"""
cam_engine/narrative/generator.py
====================================
NarrativeGenerator v2 — calls Google Gemini for all 8 CAM sections.

v2 upgrades over v1:
  - Full CMA-grade structured prompts (Parts A-E per section)
  - All financial tables injected with actual numbers
  - DSCR derivation, MPBF, GST reconciliation, capital structure
  - Parallel execution via concurrent.futures (respects rate limits)
  - Each call: 4096 max tokens (full section, not truncated)
  - Graceful degradation: failed sections return template fallback
  - New section: full Recommendation (Section 8)

Design:
  - One isolated API call per section (no shared context = no hallucination bleed)
  - Indian banking terminology enforced via SYSTEM_PROMPT
  - Sequential with 0.5s delay (Gemini Flash rate limit buffer)
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from .models import CAMNarratives, NarrativeInput
from .prompts import (
    SYSTEM_PROMPT,
    SYSTEM_PREAMBLE,
    EXECUTIVE_SUMMARY_PROMPT,
    CHARACTER_PROMPT,
    CAPACITY_PROMPT,
    CAPITAL_PROMPT,
    COLLATERAL_PROMPT,
    CONDITIONS_PROMPT,
    RISK_MITIGANTS_PROMPT,
    RECOMMENDATION_PROMPT,
)


def _safe(v, fallback=0.0):
    if v is None: return fallback
    if isinstance(v, dict): return float(v.get("value", fallback) or fallback)
    try:    return float(v)
    except: return fallback


def _pad(lst: list, n: int, fill=0.0) -> list:
    out = list(lst) + [fill] * n
    return out[:n]


def _score_band(score: int) -> str:
    if score >= 80: return "STRONG"
    if score >= 65: return "ADEQUATE"
    if score >= 45: return "CAUTIOUS"
    return "WEAK"


def _format_list(items: List[str]) -> str:
    if not items:
        return "None identified."
    return "\n".join(f"  * {i}" for i in items if i)


def _format_flags(flags: List[Dict]) -> str:
    if not flags:
        return "  * No adverse flags detected from available sources."
    rows = []
    for f in flags:
        rows.append(
            f"  [{f.get('severity','?')}] {f.get('title', f.get('description', str(f)))}"
            + (f" -- {f.get('evidence', '')}" if f.get('evidence') else "")
        )
    return "\n".join(rows)


def _format_promoters(promoters: List[Dict]) -> str:
    if not promoters:
        return "  No promoter data available."
    rows = []
    for p in promoters:
        rows.append(
            f"  {p.get('name','?')} | {p.get('designation', 'Director')} "
            f"| DIN: {p.get('din','N/A')} "
            f"| PAN: {p.get('pan','N/A')} "
            f"| Shareholding: {p.get('shareholding_pct', 0):.1f}%"
        )
    return "\n".join(rows)


def _format_collateral(assets: List[Dict]) -> str:
    if not assets:
        return "  No collateral details available. Awaiting submission."
    rows = []
    for a in assets:
        rows.append(
            f"  {a.get('type','Asset')} | "
            f"Market: Rs.{_safe(a.get('market_value')):.2f} Cr | "
            f"Distress: Rs.{_safe(a.get('distress_value')):.2f} Cr | "
            f"Charge: {a.get('charge','N/A')} | "
            f"Pledged: {'Yes - to ' + str(a.get('pledged_to','')) if a.get('pledged') else 'No'}"
        )
    return "\n".join(rows)


def _format_breakdown(breakdown: List[Dict]) -> str:
    if not breakdown:
        return "  Detailed breakdown not available."
    rows = []
    for b in breakdown:
        rows.append(f"  {b.get('label','?')} ({b.get('points',0)}/{b.get('max_points',100)} pts)")
    return "\n".join(rows)


def _format_existing_facilities(facilities: List[Dict]) -> str:
    if not facilities:
        return "  No existing credit facilities recorded."
    rows = ["  Lender          | Facility | Sanctioned  | Outstanding | Rate  | NPA?"]
    rows.append("  " + "-" * 75)
    for f in facilities:
        rows.append(
            f"  {f.get('lender','?'):<16}| "
            f"{f.get('type','CC'):<9}| "
            f"Rs.{_safe(f.get('sanctioned_amount', 0)):>8.2f}L | "
            f"Rs.{_safe(f.get('outstanding', 0)):>8.2f}L | "
            f"{f.get('rate', 'N/A'):<6}| "
            f"{f.get('npa_status', 'No')}"
        )
    return "\n".join(rows)


def _build_financial_snapshot(inp: NarrativeInput) -> str:
    """Build the financial snapshot table for Executive Summary."""
    rev   = _pad(inp.revenue,  3)
    pat   = _pad(inp.pat,      3)
    nw    = _pad(inp.net_worth_series or [inp.net_worth_cr] * 3, 3)
    td    = _pad(inp.total_debt_series or [inp.total_debt_cr] * 3, 3)
    cr    = _pad(inp.current_ratio_series, 3)
    de    = _pad(inp.de_ratio_series or [inp.de_ratio] * 3, 3)
    per   = _pad(inp.periods, 3, fill="N/A")

    def gpm(i):
        gp = inp.gross_profit[i] if i < len(inp.gross_profit) else 0.0
        return (gp / rev[i] * 100) if rev[i] > 0 else 0.0

    def npm(i):
        return (pat[i] / rev[i] * 100) if rev[i] > 0 else 0.0

    lines = [
        f"  Parameter              {per[0]:<12} {per[1]:<12} {per[2]:<12}  Trend",
        "  " + "-" * 70,
        f"  Net Sales (Rs.L)       {rev[0]:<12.2f} {rev[1]:<12.2f} {rev[2]:<12.2f}  {'↑' if rev[2]>=rev[0] else '↓'}",
        f"  GP Margin (%)          {gpm(0):<12.2f} {gpm(1):<12.2f} {gpm(2):<12.2f}  {'↑' if gpm(2)>=gpm(0) else '↓'}",
        f"  Net Profit (Rs.L)      {pat[0]:<12.2f} {pat[1]:<12.2f} {pat[2]:<12.2f}  {'↑' if pat[2]>=pat[0] else '↓'}",
        f"  NP Margin (%)          {npm(0):<12.2f} {npm(1):<12.2f} {npm(2):<12.2f}  {'↑' if npm(2)>=npm(0) else '↓'}",
        f"  Net Worth (Rs.L)       {nw[0]:<12.2f} {nw[1]:<12.2f} {nw[2]:<12.2f}  {'↑' if nw[2]>=nw[0] else '↓'}",
        f"  Total Outside Liab     {td[0]:<12.2f} {td[1]:<12.2f} {td[2]:<12.2f}  {'↑' if td[2]>=td[0] else '↓'}",
        f"  Current Ratio          {cr[0]:<12.2f} {cr[1]:<12.2f} {cr[2]:<12.2f}  {'↑' if cr[2]>=cr[0] else '↓'}",
        f"  D/E Ratio              {de[0]:<12.2f} {de[1]:<12.2f} {de[2]:<12.2f}  {'↑' if de[2]<=de[0] else '↓'}",
        f"  DSCR                   {inp.dscr:.2f}",
    ]
    return "\n".join(lines)


def _build_risk_flags_summary(inp: NarrativeInput) -> str:
    """Format research + extraction flags for Executive Summary."""
    rows = []
    for f in inp.research_flags:
        sev = f.get("severity", "MEDIUM")
        src = f.get("source", "Research")
        msg = f.get("title", f.get("description", str(f)))
        rows.append(f"  {sev:<9} | {src:<8} | {msg}")
    if not rows:
        rows.append("  POSITIVE | ALL     | No adverse flags detected across all sources.")
    return "\n".join(rows)


def _build_five_cs_table(inp: NarrativeInput) -> str:
    """Five Cs scorecard for Recommendation section."""
    def band(s):
        return "GREEN" if s >= 70 else ("AMBER" if s >= 50 else "RED")

    rows = [
        "  Five Cs           Score    Weight   Contribution  Band",
        "  " + "-" * 60,
        f"  Character         {inp.character_score:3d}/100  20%      {inp.character_score*0.20:5.1f}         {band(inp.character_score)}",
        f"  Capacity          {inp.capacity_score:3d}/100  25%      {inp.capacity_score*0.25:5.1f}         {band(inp.capacity_score)}",
        f"  Capital           {inp.capital_score:3d}/100  20%      {inp.capital_score*0.20:5.1f}         {band(inp.capital_score)}",
        f"  Collateral        {inp.collateral_score:3d}/100  15%      {inp.collateral_score*0.15:5.1f}         {band(inp.collateral_score)}",
        f"  Conditions        {inp.conditions_score:3d}/100  10%      {inp.conditions_score*0.10:5.1f}         {band(inp.conditions_score)}",
        "  " + "-" * 60,
        f"  COMPOSITE         {inp.composite_score:3d}/100  100%     {inp.composite_score:5.1f}         {inp.risk_band}",
    ]
    return "\n".join(rows)


def _build_amount_derivation_text(inp: NarrativeInput) -> str:
    """Build amount derivation chain text."""
    if inp.amount_derivation:
        return inp.amount_derivation
    if inp.amount_adjustments:
        lines = [f"  Starting point: Requested Rs.{inp.requested_cr:.2f} Cr"]
        for i, adj in enumerate(inp.amount_adjustments, 1):
            lines.append(f"  Step {i} — {adj.get('reason','')}: Rs.{_safe(adj.get('final',0))/1e7:.2f} Cr ({adj.get('detail','')})")
        lines.append(f"  Recommended amount: Rs.{inp.recommended_cr:.2f} Crore")
        return "\n".join(lines)
    return f"  Recommended amount: Rs.{inp.recommended_cr:.2f} Crore (based on composite score {inp.composite_score}/100 and MPBF compliance)"


def _build_rate_derivation_text(inp: NarrativeInput) -> str:
    """Build rate derivation chain text."""
    if inp.rate_derivation:
        return inp.rate_derivation
    lines = [
        f"  Base Rate (MCLR + Spread)  : {inp.rate_base:.2f}%",
    ]
    total = inp.rate_base
    for p in inp.rate_premiums:
        bps = _safe(p.get("bps", 0))
        pct = bps / 100
        reason = p.get("reason", p.get("label", "Risk premium"))
        if pct > 0:
            lines.append(f"  + {reason:<30}: +{pct:.2f}%")
            total += pct
    lines.append(f"  {'─'*50}")
    lines.append(f"  FINAL RATE                 : {inp.interest_rate:.2f}% p.a.")
    return "\n".join(lines)


def _ratio_assessment(val: float, warn: float, better_lower: bool = True) -> str:
    if better_lower:
        return "Within limit" if val <= warn else f"Above benchmark ({val:.2f}x vs {warn:.2f}x)"
    else:
        return "Above benchmark" if val >= warn else f"Below benchmark ({val:.2f}x vs {warn:.2f}x)"


def _build_site_visit_text(inp: NarrativeInput) -> str:
    """Build site visit data text for character section."""
    if inp.site_visit_data:
        return inp.site_visit_data
    parts = []
    if inp.factory_capacity_pct >= 0:
        parts.append(f"Factory operating at {inp.factory_capacity_pct:.0f}% capacity.")
    if inp.management_quality > 0:
        labels = {5: "Excellent", 4: "Good", 3: "Average", 2: "Below Average", 1: "Poor"}
        parts.append(f"Management quality rated {inp.management_quality}/5 ({labels.get(inp.management_quality, 'N/A')}).")
    if inp.site_condition:
        parts.append(f"Site condition: {inp.site_condition.capitalize()}.")
    if inp.key_person_risk:
        parts.append("Key-person dependency risk identified.")
    if inp.supply_chain_risk:
        parts.append("Supply chain concentration risk noted.")
    if inp.cibil_commercial_score > 0:
        parts.append(f"CIBIL Commercial Score: {inp.cibil_commercial_score:.0f}.")
    if inp.primary_insight_notes:
        parts.append(f"Credit officer notes: {inp.primary_insight_notes}")
    return " ".join(parts) if parts else "Site visit data not available."


class NarrativeGenerator:
    """
    Generates all 8 CAM section narratives using Google Gemini Flash.
    Falls back gracefully if API is unavailable.

    v2: Full CMA-grade prompts, all data injected, 4096 token limit per section.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key    = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.model      = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config={
                    "temperature":       0.15,   # very factual — avoid creativity
                    "top_p":             0.90,
                    "max_output_tokens": 4096,   # full section — no truncation
                },
            )
        except ImportError:
            self.model = None
            print("[NarrativeGenerator] google-generativeai not installed. Fallback text used.")
        except Exception as e:
            self.model = None
            print(f"[NarrativeGenerator] Gemini init failed: {e}")

    # ── Core Gemini call ───────────────────────────────────────

    def _call(self, prompt: str, section: str) -> str:
        if not self.model:
            return self._fallback(section)
        try:
            response = self.model.generate_content(prompt)
            if not response.candidates:
                return self._fallback(section, "No candidates (content policy)")
            return response.candidates[0].content.parts[0].text.strip()
        except Exception as e:
            return self._fallback(section, error=str(e))

    def _fallback(self, section: str, error: str = "") -> str:
        msg = f"[{section} narrative not available"
        if error:
            msg += f" — {error[:120]}"
        msg += ". Review the data tables in this section manually.]"
        return msg

    # ── Generate all sections ────────────────────────────────

    def generate_all(self, inp: NarrativeInput) -> CAMNarratives:
        """
        Calls Gemini sequentially for all 8 sections.
        Returns CAMNarratives with any per-section errors recorded.
        """
        results  = CAMNarratives()
        errors   = {}
        sections = [
            ("executive_summary",  self._exec_summary),
            ("character",          self._character),
            ("capacity",           self._capacity),
            ("capital",            self._capital),
            ("collateral",         self._collateral),
            ("conditions",         self._conditions),
            ("risk_mitigants",     self._risk_mitigants),
            ("recommendation",     self._recommendation),
            ("decision_rationale", self._decision_rationale),
        ]

        for attr, fn in sections:
            try:
                text = fn(inp)
                setattr(results, attr, text)
                print(f"           [Narrative] {attr}: OK ({len(text)} chars)")
            except Exception as e:
                errors[attr] = str(e)
                setattr(results, attr, self._fallback(attr, str(e)))
                print(f"           [Narrative] {attr}: ERROR — {e}")
            time.sleep(0.5)   # rate limit buffer for Gemini Flash

        results.errors = errors
        return results

    # ── Section builder methods ───────────────────────────────

    def _exec_summary(self, inp: NarrativeInput) -> str:
        financial_snapshot = _build_financial_snapshot(inp)
        risk_flags_summary = _build_risk_flags_summary(inp)
        conditions_summary = "; ".join(inp.conditions_precedent[:2]) if inp.conditions_precedent else "Standard banking conditions apply."
        amount_reason = inp.amount_reason or (
            f"Limit moderated from Rs.{inp.requested_cr:.2f} Cr based on composite score and MPBF."
            if inp.recommended_cr < inp.requested_cr else
            "Full requested amount recommended."
        )

        prompt = EXECUTIVE_SUMMARY_PROMPT.format(
            system_preamble       = SYSTEM_PROMPT,
            company_name          = inp.company_name,
            cin                   = inp.cin,
            industry              = inp.industry,
            loan_type             = inp.loan_type,
            tenor_months          = inp.tenor_months,
            requested_cr          = inp.requested_cr,
            recommended_cr        = inp.recommended_cr,
            interest_rate         = inp.interest_rate,
            risk_band             = inp.risk_band,
            composite_score       = inp.composite_score,
            decision              = inp.decision,
            financial_snapshot_table = financial_snapshot,
            risk_flags_summary    = risk_flags_summary,
            amount_reason         = amount_reason,
            conditions_summary    = conditions_summary,
        )
        return self._call(prompt, "Executive Summary")

    def _character(self, inp: NarrativeInput) -> str:
        promoter_table = _format_promoters(inp.promoters)
        lit_text       = f"{inp.litigation_count} case(s) found in eCourts" if inp.litigation_count else "No cases found in eCourts search"
        mca_text       = f"{inp.mca_flag_count} MCA flag(s) noted" if inp.mca_flag_count else "No adverse MCA findings"
        news_text      = "; ".join(inp.news_signals[:3]) if inp.news_signals else "No adverse news signals detected"
        char_flags     = _format_flags([
            f for f in inp.research_flags
            if f.get("category") in ("PROMOTER", "FRAUD", "LITIGATION")
        ])
        site_visit_text = _build_site_visit_text(inp)

        prompt = CHARACTER_PROMPT.format(
            system_preamble    = SYSTEM_PROMPT,
            company_name       = inp.company_name,
            cin                = inp.cin,
            industry           = inp.industry,
            character_score    = inp.character_score,
            character_band     = _score_band(inp.character_score),
            promoter_table     = promoter_table,
            rbi_result         = inp.rbi_result,
            litigation_summary = lit_text,
            mca_summary        = mca_text,
            news_summary       = news_text,
            character_flags    = char_flags,
            site_visit_data    = site_visit_text,
        )
        return self._call(prompt, "Character")

    def _capacity(self, inp: NarrativeInput) -> str:
        rev   = _pad(inp.revenue,           3)
        gp    = _pad(inp.gross_profit,       3)
        ebitda= _pad(inp.ebitda,             3)
        fc    = _pad(inp.finance_charges,    3)
        pat   = _pad(inp.pat,               3)
        cfo   = _pad(inp.cfo,               3)
        nw    = _pad(inp.net_worth_series or [inp.net_worth_cr] * 3, 3)
        td    = _pad(inp.total_debt_series  or [inp.total_debt_cr] * 3, 3)
        cr    = _pad(inp.current_ratio_series, 3)
        de    = _pad(inp.de_ratio_series or [inp.de_ratio] * 3, 3)
        per   = _pad(inp.periods, 3, fill="N/A")

        def gpm(i): return (gp[i] / rev[i] * 100) if rev[i] > 0 else 0.0
        def npm(i): return (pat[i] / rev[i] * 100) if rev[i] > 0 else 0.0
        def ebitdam(i): return (ebitda[i] / rev[i] * 100) if rev[i] > 0 else 0.0

        dep3    = inp.depreciation_latest
        fc3     = fc[2]
        pat3    = pat[2]
        cash_accrual = inp.cash_accrual or (pat3 + dep3 + fc3)
        debt_service = inp.debt_service  or (inp.tl_repayment_latest + fc3)
        dscr    = (cash_accrual / debt_service) if debt_service > 0 else inp.dscr
        cfo_pat = (cfo[2] / pat[2]) if pat[2] != 0 else inp.cfo_pat_ratio

        concerns = "; ".join([
            f.get("title", str(f)) for f in inp.research_flags
            if f.get("category") == "FINANCIAL"
        ][:2]) or "None identified."

        prompt = CAPACITY_PROMPT.format(
            system_preamble    = SYSTEM_PROMPT,
            company_name       = inp.company_name,
            capacity_score     = inp.capacity_score,
            capacity_band      = _score_band(inp.capacity_score),
            period_1=per[0], period_2=per[1], period_3=per[2],
            rev_1=rev[0],   rev_2=rev[1],    rev_3=rev[2],
            gp_1=gp[0],    gp_2=gp[1],      gp_3=gp[2],
            gp_m_1=gpm(0), gp_m_2=gpm(1),   gp_m_3=gpm(2),
            ebitda_1=ebitda[0], ebitda_2=ebitda[1], ebitda_3=ebitda[2],
            ebitda_m_1=ebitdam(0), ebitda_m_2=ebitdam(1), ebitda_m_3=ebitdam(2),
            fc_1=fc[0],    fc_2=fc[1],       fc_3=fc3,
            pat_1=pat[0],  pat_2=pat[1],     pat_3=pat3,
            np_m_1=npm(0), np_m_2=npm(1),    np_m_3=npm(2),
            rev_cagr       = inp.rev_cagr,
            nw_1=nw[0],    nw_2=nw[1],       nw_3=nw[2],
            td_1=td[0],    td_2=td[1],       td_3=td[2],
            cr_1=cr[0],    cr_2=cr[1],       cr_3=cr[2],
            de_1=de[0],    de_2=de[1],       de_3=de[2],
            cfo_1=cfo[0],  cfo_2=cfo[1],     cfo_3=cfo[2],
            dscr           = max(dscr, inp.dscr),
            icr            = inp.icr,
            cfo_pat_ratio  = cfo_pat,
            dep_3          = dep3,
            tl_repayment   = inp.tl_repayment_latest,
            cash_accrual   = cash_accrual,
            debt_service   = debt_service,
            tca            = inp.total_current_assets,
            cl_exbank      = inp.current_liab_ex_bank,
            wc_gap         = inp.wc_gap,
            proposed_cc    = inp.proposed_cc,
            mpbf           = inp.mpbf,
            within_mpbf    = inp.within_mpbf,
            within_mpbf_margin = inp.within_mpbf_margin,
            capacity_breakdown = _format_breakdown(inp.capacity_breakdown),
            capacity_concerns  = concerns,
        )
        return self._call(prompt, "Capacity")

    def _capital(self, inp: NarrativeInput) -> str:
        per   = _pad(inp.periods, 3, fill="N/A")
        n     = 3
        sc    = _pad(inp.share_capital_series,    n)
        rs    = _pad(inp.reserves_surplus_series, n)
        nw    = _pad(inp.net_worth_series or [inp.net_worth_cr] * n, n)
        tl    = _pad(inp.term_loan_series,        n)
        cc_os = _pad(inp.cc_outstanding_series,   n)
        tol   = _pad(inp.tol_series,              n)
        tnw   = _pad(inp.tnw_series or [inp.tangible_nw_cr] * n, n)
        tol_tnw = _pad(inp.tol_tnw_series,        n)
        de    = _pad(inp.de_ratio_series or [inp.de_ratio] * n, n)

        prompt = CAPITAL_PROMPT.format(
            system_preamble       = SYSTEM_PROMPT,
            company_name          = inp.company_name,
            capital_score         = inp.capital_score,
            capital_band          = _score_band(inp.capital_score),
            period_1=per[0], period_2=per[1], period_3=per[2],
            sc_1=sc[0],   sc_2=sc[1],   sc_3=sc[2],
            rs_1=rs[0],   rs_2=rs[1],   rs_3=rs[2],
            nw_1=nw[0],   nw_2=nw[1],   nw_3=nw[2],
            tl_1=tl[0],   tl_2=tl[1],   tl_3=tl[2],
            cc_os_1=cc_os[0], cc_os_2=cc_os[1], cc_os_3=cc_os[2],
            tol_1=tol[0], tol_2=tol[1], tol_3=tol[2],
            tnw_1=tnw[0], tnw_2=tnw[1], tnw_3=tnw[2],
            tol_tnw_1=tol_tnw[0], tol_tnw_2=tol_tnw[1], tol_tnw_3=tol_tnw[2],
            de_1=de[0],   de_2=de[1],   de_3=de[2],
            promoter_shareholding  = inp.promoter_shareholding,
            unsecured_loans        = inp.unsecured_loans,
            existing_facilities_table = _format_existing_facilities(inp.existing_facilities),
            capital_breakdown      = _format_breakdown(inp.capital_breakdown),
        )
        return self._call(prompt, "Capital")

    def _collateral(self, inp: NarrativeInput) -> str:
        prompt = COLLATERAL_PROMPT.format(
            system_preamble    = SYSTEM_PROMPT,
            company_name       = inp.company_name,
            collateral_score   = inp.collateral_score,
            collateral_band    = _score_band(inp.collateral_score),
            requested_cr       = inp.requested_cr,
            recommended_cr     = inp.recommended_cr,
            collateral_table   = _format_collateral(inp.collateral_assets),
            total_market_cr    = inp.total_market_cr,
            total_distress_cr  = inp.total_distress_cr,
            coverage_market    = inp.coverage_market,
            coverage_distress  = inp.coverage_distress,
            guarantors_text    = inp.guarantors_text or "Personal guarantee of all promoters.",
            collateral_breakdown = _format_breakdown(inp.collateral_breakdown),
        )
        return self._call(prompt, "Collateral")

    def _conditions(self, inp: NarrativeInput) -> str:
        sector_flags  = _format_list([
            f.get("title", str(f)) for f in inp.research_flags
            if f.get("category") == "SECTOR"
        ])
        reg_notes = _format_list([
            f.get("title", str(f)) for f in inp.research_flags
            if f.get("category") == "REGULATORY"
        ]) or "No specific regulatory flags identified."
        bank_spread = inp.bank_spread or float(os.getenv("BANK_SPREAD", "3.00"))

        prompt = CONDITIONS_PROMPT.format(
            system_preamble      = SYSTEM_PROMPT,
            company_name         = inp.company_name,
            industry             = inp.industry,
            conditions_score     = inp.conditions_score,
            conditions_band      = _score_band(inp.conditions_score),
            sector_score         = inp.sector_score,
            news_signals         = "; ".join(inp.news_signals[:4]) if inp.news_signals else "No adverse signals",
            sector_flags         = sector_flags or "No sector-specific flags.",
            regulatory_notes     = reg_notes,
            gstn_status          = inp.gstn_status or "Active",
            gst_compliance_pct   = inp.gst_compliance_pct,
            gst_turnover         = inp.gst_turnover,
            bank_credits         = inp.bank_credits,
            gst_bank_ratio       = inp.gst_bank_ratio if inp.gst_bank_ratio > 0 else (
                                       inp.gst_turnover / inp.bank_credits
                                       if inp.bank_credits > 0 else 0.0),
            gstr2a_itc           = inp.gstr2a_itc,
            gstr3b_itc           = inp.gstr3b_itc,
            itc_variance_pct     = inp.itc_variance_pct,
            repo_rate            = inp.repo_rate,
            base_rate            = inp.rate_base,
            spread               = bank_spread,
        )
        return self._call(prompt, "Conditions")

    def _risk_mitigants(self, inp: NarrativeInput) -> str:
        risk_rows = []
        for f in inp.research_flags:
            if f.get("severity") in ("HIGH", "MEDIUM", "CRITICAL"):
                risk_rows.append(
                    f"  Risk: {f.get('title', str(f))} [{f.get('severity')}]\n"
                    f"  Evidence: {f.get('description', f.get('evidence', 'See research report'))}\n"
                    f"  Mitigant: {_default_mitigant(f)}"
                )
        risk_table = "\n\n".join(risk_rows) or "No significant risks identified."

        cr_l    = inp.current_ratio_series[-1] if inp.current_ratio_series else 0.0
        de_l    = inp.de_ratio_series[-1] if inp.de_ratio_series else inp.de_ratio
        tol_tnw_l = inp.tol_tnw_series[-1] if inp.tol_tnw_series else 0.0

        cond_list = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(inp.conditions_precedent))
        cov_list  = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(inp.covenants))

        prompt = RISK_MITIGANTS_PROMPT.format(
            system_preamble     = SYSTEM_PROMPT,
            company_name        = inp.company_name,
            decision            = inp.decision,
            recommended_cr      = inp.recommended_cr,
            interest_rate       = inp.interest_rate,
            composite_score     = inp.composite_score,
            risk_mitigant_table = risk_table,
            cr_latest           = cr_l,
            de_latest           = de_l,
            dscr                = inp.dscr,
            icr                 = inp.icr,
            tol_tnw_latest      = tol_tnw_l,
            cr_assessment       = _ratio_assessment(cr_l, 1.25, better_lower=False),
            de_assessment       = _ratio_assessment(de_l, 3.0,  better_lower=True),
            dscr_assessment     = _ratio_assessment(inp.dscr, 1.25, better_lower=False),
            icr_assessment      = _ratio_assessment(inp.icr,  2.0,  better_lower=False),
            tol_tnw_assessment  = _ratio_assessment(tol_tnw_l, 3.0, better_lower=True),
            coverage_market     = inp.coverage_market,
            conditions_list     = cond_list or "  Standard banking conditions apply.",
            covenants_list      = cov_list  or "  Standard covenant package applies.",
        )
        return self._call(prompt, "Risk Mitigants")

    def _recommendation(self, inp: NarrativeInput) -> str:
        five_cs_table    = _build_five_cs_table(inp)
        amount_derivation = _build_amount_derivation_text(inp)
        rate_derivation  = _build_rate_derivation_text(inp)
        rate_build_up    = inp.rate_build_up or f"{inp.rate_base:.2f}% base + premiums = {inp.interest_rate:.2f}% p.a."
        mpbf_compliance  = inp.mpbf_compliance or (
            f"Within MPBF — Proposed CC Rs.{inp.proposed_cc:.2f}L within MPBF of Rs.{inp.mpbf:.2f}L"
            if inp.mpbf > 0 else "MPBF computation pending"
        )
        cond_list = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(inp.conditions_precedent))
        cov_list  = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(inp.covenants))

        prompt = RECOMMENDATION_PROMPT.format(
            system_preamble   = SYSTEM_PROMPT,
            company_name      = inp.company_name,
            composite_score   = inp.composite_score,
            risk_band         = inp.risk_band,
            decision          = inp.decision,
            five_cs_table     = five_cs_table,
            loan_type         = inp.loan_type,
            recommended_cr    = inp.recommended_cr,
            requested_cr      = inp.requested_cr,
            interest_rate     = inp.interest_rate,
            tenor_months      = inp.tenor_months,
            rate_build_up     = rate_build_up,
            mpbf_compliance   = mpbf_compliance,
            amount_derivation = amount_derivation,
            rate_derivation   = rate_derivation,
            conditions_list   = cond_list or "  Standard banking conditions apply.",
            covenants_list    = cov_list  or "  Standard covenant package applies.",
        )
        return self._call(prompt, "Recommendation")

    def _decision_rationale(self, inp: NarrativeInput) -> str:
        """Cross-pillar explainability narrative — AI explains WHY the decision was made."""
        qi_text = ""
        if inp.qualitative_explanations:
            qi_text = "Primary Insight adjustments applied:\n" + "\n".join(inp.qualitative_explanations)
        elif inp.factory_capacity_pct >= 0:
            qi_text = f"Factory capacity observed at {inp.factory_capacity_pct:.0f}%."
            if inp.management_quality > 0:
                qi_text += f" Management quality rated {inp.management_quality}/5."

        contradictions_text = ""
        if inp.cross_pillar_contradictions:
            contradictions_text = "Cross-pillar contradictions identified:\n" + \
                "\n".join(f"  - {c}" for c in inp.cross_pillar_contradictions)

        cibil_text = ""
        if inp.cibil_commercial_score > 0:
            cibil_text = f"CIBIL Commercial Score: {inp.cibil_commercial_score:.0f}."

        prompt = f"""{SYSTEM_PROMPT}

You are writing the DECISION RATIONALE section of a Credit Appraisal Memo (CAM) for {inp.company_name}.
This section must clearly explain the credit decision in plain language, citing specific evidence
from EACH of the three pillars of analysis:
  Pillar 1 — Document extraction (financial metrics)
  Pillar 2 — Research intelligence (RBI, MCA, eCourts, news)
  Pillar 3 — Scoring engine (composite score, qualitative observations)

DECISION: {inp.decision}
COMPOSITE SCORE: {inp.composite_score}/100  (Risk Band: {inp.risk_band})
RECOMMENDED AMOUNT: Rs.{inp.recommended_cr:.2f} Cr (Requested: Rs.{inp.requested_cr:.2f} Cr)
INTEREST RATE: {inp.interest_rate:.2f}% p.a.

FINANCIAL HIGHLIGHTS (Pillar 1 — Document Extraction):
  Revenue CAGR: {inp.rev_cagr:.1f}%
  DSCR: {inp.dscr:.2f}x  |  ICR: {inp.icr:.2f}x
  Capacity Score: {inp.capacity_score}/100  |  Capital Score: {inp.capital_score}/100
  Collateral Coverage (Market): {inp.coverage_market:.2f}x
  GST Filing Compliance: {inp.gst_compliance_pct:.1f}%

RESEARCH INTELLIGENCE (Pillar 2):
  Character Score: {inp.character_score}/100  |  Conditions Score: {inp.conditions_score}/100
  Litigation findings: {inp.litigation_count} case(s) via eCourts
  MCA flags: {inp.mca_flag_count}
  RBI check: {inp.rbi_result}
  News signals: {'; '.join(inp.news_signals[:3]) if inp.news_signals else 'None adverse'}

PRIMARY INSIGHTS (Pillar 3 — Credit Officer Field Observations):
{qi_text if qi_text else '  No qualitative field data entered.'}
{cibil_text}

{contradictions_text}

Write a 3-5 paragraph analytical narrative that:
1. Opens with the decision and the single most important reason (cite specific metric/finding)
2. Explains the primary driving factors — financial and research — with specific numbers
3. If any contradictions exist between pillars, explicitly mention and explain them
4. Explains how qualitative field observations influenced the final score (if applicable)
5. Concludes with the recommended lending terms and key conditions

Use precise Indian banking language. Do NOT use bullet points — write in flowing paragraphs.
Use past tense for actuals. Cite actual numbers (DSCR, D/E, GST compliance %, etc.)."""

        return self._call(prompt, "Decision Rationale")


# ── Mitigant helper ──────────────────────────────────────────

def _default_mitigant(flag: Dict) -> str:
    cat = flag.get("category", "")
    sev = flag.get("severity", "MEDIUM")
    if cat == "LITIGATION":
        return "Legal proceedings to be monitored via eCourts; legal opinion to be obtained pre-disbursement; indemnity from promoters."
    if cat == "FINANCIAL":
        return "Financial covenants, quarterly monitoring statements, and right of recall on covenant breach."
    if cat == "REGULATORY":
        return "Compliance rectification required as condition precedent; NOC from relevant authority to be submitted."
    if cat == "PROMOTER":
        return "Enhanced promoter due-diligence; personal guarantee with net worth affidavit to be obtained."
    if cat == "SECTOR":
        return "Sector risk partially offset by company-specific strengths; annual sector review and ESI covenant."
    if cat == "FRAUD" or sev == "CRITICAL":
        return "ESCALATE TO CREDIT COMMITTEE IMMEDIATELY — do not process further without committee approval."
    return "Enhanced monitoring covenant package, quarterly review, and site visits at bank's discretion."
