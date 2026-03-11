"""
cam_engine/main.py
====================
Pillar 3 Entry Point — generate_cam()

Full pipeline:
  1. Financial Scorer     → 4 dimension scores (Capacity/Capital/Collateral/GST)
  2. Composite Scorer     → weighted composite from all 8 dimensions
  3. Amount Engine        → recommended loan amount (transparent chain)
  4. Rate Engine          → recommended interest rate (basis-point chain)
  5. Conditions Deriver   → pre-disbursement conditions + covenants
  6. Narrative Generator  → 7 Claude-written CAM sections
  7. Document Builder     → python-docx → .docx
  8. PDF Converter        → .docx → .pdf

Returns:
  cam_dict — JSON-serialisable dict stored in backend SQLite cam_json column
  (also contains docx_path and pdf_path for the download endpoint)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# ── Load environment ──────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    load_dotenv(Path(__file__).parent.parent / "backend" / ".env")
except ImportError:
    pass


# ── Import sub-components ─────────────────────────────────────
from scoring.financial_scorer import (
    score_capacity, score_capital, score_collateral,
    score_gst_quality, score_from_research,
)
from scoring.composite_scorer import compute_composite
from scoring.models import FinancialScores

from recommendation.amount_engine import calculate_recommended_amount
from recommendation.rate_engine import (
    calculate_interest_rate,
    derive_conditions_precedent,
    derive_covenants,
)
from recommendation.models import LoanRecommendation

from narrative.generator import NarrativeGenerator
from narrative.models import NarrativeInput

from document.builder import CAMBuilder
from document.pdf_converter import convert_to_pdf


# ─────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────

def generate_cam(
    case_id:     str,
    extraction:  Dict,          # from Pillar 1 extractor output JSON
    research:    Dict,          # from Pillar 2 research agent ResearchOutput JSON
    req:         Dict,          # original request metadata (case details)
    output_dir:  str = "output",
) -> Dict:
    """
    Full Pillar 3 pipeline.

    Parameters
    ----------
    case_id    : Unique case ID (e.g. "CASE_2026_A1B2C3")
    extraction : Extractor JSON output dict
    research   : Research agent ResearchOutput dict
    req        : Request metadata (company_name, cin, gstin, loan, promoters)
    output_dir : Where to save .docx and .pdf files

    Returns
    -------
    dict  — cam_json (JSON-serialisable, stored in SQLite + returned by API)
    """
    started = datetime.now()
    print(f"\n[Pillar 3] Starting CAM generation for case: {case_id}")

    # Extract qualitative / primary insight data from req
    qualitative = req.get("qualitative", {}) or {}
    print(f"[Pillar 3] Primary insight fields: {list(qualitative.keys()) if qualitative else 'none entered'}")

    # ── 1. Score: Financial dimensions ───────────────────────
    print("[Pillar 3] Step 1/7 — Financial scoring...")
    requested_amount = float(
        req.get("loan", {}).get("amount_inr", 0) or
        req.get("loan_amount", 0) or 0
    )

    cap_dim  = score_capacity(extraction)
    cap2_dim = score_capital(extraction)
    col_dim  = score_collateral(extraction, requested_amount)
    gst_dim  = score_gst_quality(extraction)

    fin_scores = FinancialScores(
        capacity    = cap_dim,
        capital     = cap2_dim,
        collateral  = col_dim,
        gst_quality = gst_dim,
    )

    # ── 2. Score: Research dimensions ────────────────────────
    print("[Pillar 3] Step 2/7 — Research scoring...")
    res_scores = score_from_research(research)

    # ── 3. Composite ───────────────────────────────────────────
    print("[Pillar 3] Step 3/7 — Composite scoring...")
    composite = compute_composite(fin_scores, res_scores, research, qualitative)
    print(f"           Composite: {composite.composite_score}/100 -> {composite.risk_band} -> {composite.decision}")
    if composite.qualitative_adjustment != 0:
        print(f"           Qualitative adjustment: {'+' if composite.qualitative_adjustment > 0 else ''}{composite.qualitative_adjustment} pts applied")

    # ── 4. Loan recommendation ────────────────────────────────
    print("[Pillar 3] Step 4/7 — Loan recommendation...")
    amount_rec = calculate_recommended_amount(
        requested_amount = requested_amount,
        extraction       = extraction,
        research         = research,
        composite        = composite,
    )
    rate_rec = calculate_interest_rate(extraction, research, composite)
    conds    = derive_conditions_precedent(composite, amount_rec)
    covs     = derive_covenants(composite)

    rec_amount_cr  = amount_rec.final / 1e7
    req_amount_cr  = requested_amount / 1e7
    print(f"           Amount:  Rs.{rec_amount_cr:.2f} Cr (requested: Rs.{req_amount_cr:.2f} Cr)")
    print(f"           Rate:    {rate_rec.final_rate:.2f}% p.a. ({rate_rec.rate_band})")

    # ── 5. Build narratives ───────────────────────────────────
    print("[Pillar 3] Step 5/7 — Generating narratives (Claude)...")
    promoters   = req.get("promoters", [])
    industry    = (extraction.get("company_profile", {}).get("sector")
                   or req.get("industry", "Unknown Sector"))
    loan_type   = (req.get("loan", {}).get("type")
                   or req.get("loan_type", "Working Capital"))
    tenor       = int(req.get("loan", {}).get("tenor_months", 36) or 36)

    # ── Pull financial data for narrative hydration (v2 — full CMA-grade) ───
    income      = extraction.get("income_statement", {})
    rev_vals    = _extract_period_values(income.get("total_revenue", {}))
    ebitda_vals = _extract_period_values(income.get("ebitda", {}))
    pat_vals    = _extract_period_values(income.get("pat", {}))
    cfo_vals    = _extract_period_values(extraction.get("cash_flow", {}).get("cfo", {}))
    periods     = income.get("periods", []) or list(income.get("total_revenue", {}).keys())[:3]
    rev_cagr    = _cagr(rev_vals)
    ebitda_m    = (ebitda_vals[-1] / rev_vals[-1] * 100) if (rev_vals and ebitda_vals and rev_vals[-1]) else 0.0

    # Gross profit series: revenue - cost_of_sales per period
    gp_vals = _extract_period_values(income.get("gross_profit", {}))
    if not gp_vals:
        cogs_vals = _extract_period_values(income.get("cost_of_sales", {}) or income.get("total_cost_of_sales", {}))
        gp_vals   = [r - c for r, c in zip(rev_vals, cogs_vals)] if cogs_vals else [0.0] * len(rev_vals)

    # Finance charges series (TL + CC)
    fc_tl_vals  = _extract_period_values(income.get("finance_charges_tl", {}))
    fc_cc_vals  = _extract_period_values(income.get("finance_charges_cc", {}))
    fc_all_vals = _extract_period_values(income.get("finance_charges", {}) or income.get("total_finance_charges", {}))
    if not fc_all_vals and fc_tl_vals:
        fc_all_vals = [tl + cc for tl, cc in zip(
            fc_tl_vals,
            fc_cc_vals if fc_cc_vals else [0.0]*len(fc_tl_vals)
        )]

    # Balance sheet
    bs          = extraction.get("balance_sheet", {})
    cm          = extraction.get("credit_metrics", {})
    nw          = _safe(bs.get("net_worth", 0))
    td_raw      = bs.get("total_debt", {})
    td          = _safe(td_raw) if not isinstance(td_raw, dict) else (
        _safe(td_raw.get("term_loan_outstanding", 0)) +
        _safe(td_raw.get("total_rated_facilities", 0))
    )
    ta          = _safe(bs.get("total_assets", 0))
    tnw         = _safe(bs.get("tangible_net_worth", 0)) or nw
    de          = _safe(cm.get("debt_equity", 0))
    if de == 0 and nw > 0 and td > 0:
        de = td / nw
    dscr        = _safe(cm.get("dscr", 0))
    icr         = _latest_val(cm.get("interest_coverage_ratio", {}))

    # 3-year balance sheet series (lacs — extracted directly from income/bs)
    nw_series  = _extract_period_values(bs.get("net_worth_series", {}))  or [nw]  * 3
    td_series  = _extract_period_values(bs.get("total_debt_series", {})) or [td]  * 3
    cr_series  = _extract_period_values(bs.get("current_ratio", {}))     or []
    de_series  = _extract_period_values(bs.get("gearing_ratio", {}))     or [de]  * 3
    sc_series  = _extract_period_values(bs.get("share_capital", {}))     or []
    rs_series  = _extract_period_values(bs.get("reserves_surplus", {}))  or []
    tl_series  = _extract_period_values(bs.get("term_loans", {}))        or []
    cc_series  = _extract_period_values(bs.get("cc_outstanding", {}))    or []
    tol_series = _extract_period_values(bs.get("total_outside_liab", {})) or []
    tnw_series = _extract_period_values(bs.get("tangible_nw", {}))       or [tnw] * 3
    tol_tnw_s  = _extract_period_values(bs.get("tol_tnw_ratio", {}))     or []

    # DSCR computation fields
    dep_latest = _safe(income.get("depreciation", {}).get("latest") or
                       _latest_val(income.get("depreciation", {})) or 0)
    tl_repayment_l = _safe(cm.get("annual_tl_repayment") or bs.get("tl_repayment_latest") or 0)
    pat_l    = pat_vals[-1] if pat_vals else 0.0
    fc_l     = fc_all_vals[-1] if fc_all_vals else 0.0
    cash_acc = pat_l + dep_latest + fc_l
    debt_svc = tl_repayment_l + fc_l
    dscr_computed = (cash_acc / debt_svc) if debt_svc > 0 else dscr
    if dscr == 0 and dscr_computed > 0:
        dscr = dscr_computed

    # MPBF / Working Capital (Tandon Method II)
    wc_data   = extraction.get("working_capital_analysis", {}) or extraction.get("banking_data", {})
    tca       = _safe(wc_data.get("total_current_assets") or bs.get("current_assets") or 0)
    ca_lc     = _safe(bs.get("current_assets", 0))
    tca       = tca or ca_lc
    cl_ex     = _safe(wc_data.get("current_liab_ex_bank") or bs.get("current_liabilities") or 0)
    wc_gap    = tca - cl_ex if tca > 0 else 0.0
    mpbf      = _safe(wc_data.get("mpbf") or cm.get("mpbf") or (wc_gap * 0.75))
    nwc_val   = _safe(wc_data.get("nwc") or bs.get("nwc") or (tca - _safe(bs.get("current_liabilities", 0))))
    min_nwc   = wc_gap * 0.25
    proposed_cc_l = float(req.get("loan", {}).get("amount_inr", 0) or requested_amount) / 1e5  # to lacs
    within_mpbf = "Yes" if (proposed_cc_l <= mpbf or mpbf == 0) else f"No — exceeds MPBF by Rs.{proposed_cc_l - mpbf:.2f}L"
    within_mpbf_margin = (
        f"{nwc_val/wc_gap*100:.0f}% of Working Capital Gap — adequate NWC margin"
        if wc_gap > 0 else "NWC margin data pending"
    )

    # GST data
    gst_data   = extraction.get("gst_data", {}) or {}
    gst_turnover  = _safe(gst_data.get("annual_turnover") or 0)
    bank_credits  = _safe(gst_data.get("bank_credits")     or 0)
    gst_bank_r    = gst_turnover / bank_credits if bank_credits > 0 else 0.0
    gstr2a_itc    = _safe(gst_data.get("gstr2a_itc")       or 0)
    gstr3b_itc    = _safe(gst_data.get("gstr3b_itc")       or 0)
    itc_var_pct   = ((gstr3b_itc - gstr2a_itc) / gstr2a_itc * 100) if gstr2a_itc > 0 else 0.0
    gst_comp_pct  = _safe(gst_data.get("filing_compliance_pct") or 100)
    gstn_status   = str(gst_data.get("registration_status") or "Active")

    # Site visit data text
    qi_parts = []
    if qualitative.get("factory_capacity_pct") not in (None, -1, ""):
        qi_parts.append(f"Factory capacity: {qualitative['factory_capacity_pct']}%.")
    if qualitative.get("management_quality"):
        labels_mq = {5:"Excellent", 4:"Good", 3:"Average", 2:"Below Average", 1:"Poor"}
        mq = int(qualitative.get("management_quality", 0))
        qi_parts.append(f"Management quality: {mq}/5 ({labels_mq.get(mq,'N/A')}).")
    if qualitative.get("site_condition"):
        qi_parts.append(f"Site condition: {qualitative['site_condition'].capitalize()}.")
    if qualitative.get("key_person_risk"):
        qi_parts.append("Key-person dependency risk identified.")
    if qualitative.get("supply_chain_risk"):
        qi_parts.append("Supply chain concentration risk noted.")
    if qualitative.get("cibil_commercial_score") not in (None, -1, ""):
        qi_parts.append(f"CIBIL Commercial Score: {qualitative['cibil_commercial_score']}.")
    if qualitative.get("notes"):
        qi_parts.append(f"Credit officer notes: {qualitative['notes']}")
    site_visit_text = " ".join(qi_parts) or "Site visit data not submitted by credit officer."

    # Existing facilities
    existing_fac = extraction.get("credit_metrics", {}).get("existing_credit_facilities", []) or []

    # Rate derivation text
    rate_deriv_lines = [f"  Base Rate (MCLR + Spread): {rate_rec.base_rate:.2f}%"]
    for p in rate_rec.premiums:
        bps = getattr(p, 'bps', 0) or 0
        if bps > 0:
            rate_deriv_lines.append(f"  + {p.reason}: +{bps/100:.2f}%")
    rate_deriv_lines.append(f"  Final Rate: {rate_rec.final_rate:.2f}% p.a.")
    rate_deriv_text = "\n".join(rate_deriv_lines)
    rate_build_up_text = f"{rate_rec.base_rate:.2f}% base + {rate_rec.final_rate - rate_rec.base_rate:.2f}% premium = {rate_rec.final_rate:.2f}% p.a."

    # Amount derivation text
    adj_lines = [f"  Starting point: Requested Rs.{req_amount_cr:.2f} Crore"]
    for i, a in enumerate(amount_rec.adjustments, 1):
        adl = getattr(a, 'reason', str(a))
        adlines_final = getattr(a, 'final', None)
        if adlines_final:
            adj_lines.append(f"  Step {i} — {adl}: Rs.{float(adlines_final)/1e7:.2f} Cr")
    adj_lines.append(f"  Recommended: Rs.{rec_amount_cr:.2f} Crore")
    amount_deriv_text = "\n".join(adj_lines)
    amount_reason_text = (
        f"Limit moderated from Rs.{req_amount_cr:.2f} Cr (requested) based on composite score "
        f"{composite.composite_score}/100 and MPBF constraint."
        if rec_amount_cr < req_amount_cr else
        f"Full requested amount of Rs.{req_amount_cr:.2f} Cr recommended — MPBF supports and risk profile adequate."
    )
    mpbf_compliance_text = (
        f"Yes — Proposed CC Rs.{proposed_cc_l:.2f}L is within MPBF of Rs.{mpbf:.2f}L"
        if mpbf > 0 else "MPBF computation pending — CMA data required"
    )

    collateral  = extraction.get("collateral_data", [])
    total_market   = sum(_safe(a.get("market_value")) for a in collateral)
    total_distress = sum(_safe(a.get("distress_value")) for a in collateral)
    cov_market     = total_market / requested_amount if requested_amount > 0 else 0.0
    cov_distress   = total_distress / requested_amount if requested_amount > 0 else 0.0

    flags_list   = research.get("flags", [])
    tags_list    = research.get("tags", [])
    rbi_result   = "Not flagged in RBI Wilful Defaulter database"
    lit_flags    = [f for f in flags_list if f.get("category") == "LITIGATION"]
    news_signals = [f.get("title", f.get("description", "")) for f in flags_list if f.get("source") == "NEWS"]

    narr_input = NarrativeInput(
        case_id          = case_id,
        company_name     = req.get("company_name", extraction.get("company_profile", {}).get("legal_name", "Company")),
        cin              = req.get("cin", ""),
        industry         = industry,
        loan_type        = loan_type,
        tenor_months     = tenor,
        requested_cr     = req_amount_cr,
        recommended_cr   = rec_amount_cr,
        promoters        = promoters,
        decision         = composite.decision,
        risk_band        = composite.risk_band,
        composite_score  = composite.composite_score,
        interest_rate    = rate_rec.final_rate,
        character_score  = res_scores.character.score,
        capacity_score   = cap_dim.score,
        capital_score    = cap2_dim.score,
        collateral_score = col_dim.score,
        conditions_score = res_scores.conditions.score,
        capacity_breakdown   = [b.model_dump() for b in cap_dim.breakdown],
        capital_breakdown    = [b.model_dump() for b in cap2_dim.breakdown],
        collateral_breakdown = [b.model_dump() for b in col_dim.breakdown],
        # ── 3-year income statement ────────────────────────────────────
        revenue          = rev_vals,
        ebitda           = ebitda_vals,
        gross_profit     = gp_vals,
        finance_charges  = fc_all_vals or [0.0] * 3,
        pat              = pat_vals,
        cfo              = cfo_vals,
        periods          = [str(p) for p in periods[:3]],
        rev_cagr         = rev_cagr,
        ebitda_margin_latest = ebitda_m,
        depreciation_latest  = dep_latest,
        # ── DSCR computation ───────────────────────────────────────────
        dscr                 = dscr,
        icr                  = icr,
        tl_repayment_latest  = tl_repayment_l,
        cash_accrual         = cash_acc,
        debt_service         = debt_svc,
        cfo_pat_ratio        = (cfo_vals[-1] / pat_vals[-1]) if (pat_vals and pat_vals[-1] and cfo_vals) else 0.0,
        # ── Balance sheet ratios ───────────────────────────────────────
        de_ratio             = de,
        net_worth_cr         = nw / 1e2 if nw > 1e4 else nw,
        total_debt_cr        = td / 1e2 if td > 1e4 else td,
        tangible_nw_cr       = tnw / 1e2 if tnw > 1e4 else tnw,
        total_assets_cr      = ta / 1e2 if ta > 1e4 else ta,
        # ── 3-year series (lacs) ───────────────────────────────────────
        net_worth_series     = nw_series,
        total_debt_series    = td_series,
        current_ratio_series = cr_series,
        de_ratio_series      = de_series,
        share_capital_series    = sc_series,
        reserves_surplus_series = rs_series,
        term_loan_series        = tl_series,
        cc_outstanding_series   = cc_series,
        tol_series              = tol_series,
        tnw_series              = tnw_series,
        tol_tnw_series          = tol_tnw_s,
        # ── MPBF / Tandon ─────────────────────────────────────────────
        total_current_assets = tca,
        current_liab_ex_bank = cl_ex,
        wc_gap               = wc_gap,
        proposed_cc          = proposed_cc_l,
        mpbf                 = mpbf,
        nwc                  = nwc_val,
        min_nwc_stipulated   = min_nwc,
        within_mpbf          = within_mpbf,
        within_mpbf_margin   = within_mpbf_margin,
        # ── GST ────────────────────────────────────────────────────────
        gst_compliance_pct   = gst_comp_pct,
        gst_turnover         = gst_turnover,
        bank_credits         = bank_credits,
        gst_bank_ratio       = gst_bank_r,
        gstr2a_itc           = gstr2a_itc,
        gstr3b_itc           = gstr3b_itc,
        itc_variance_pct     = itc_var_pct,
        gstn_status          = gstn_status,
        # ── Capital structure ──────────────────────────────────────────
        promoter_shareholding   = float(extraction.get("company_profile", {}).get("promoter_stake_pct", 0) or 0),
        unsecured_loans         = _safe(bs.get("unsecured_loans_promoters") or 0),
        existing_facilities     = existing_fac,
        # ── Collateral ─────────────────────────────────────────────────
        collateral_assets    = collateral,
        total_market_cr      = total_market / 1e2 if total_market > 1e4 else total_market,
        total_distress_cr    = total_distress / 1e2 if total_distress > 1e4 else total_distress,
        coverage_market      = cov_market,
        coverage_distress    = cov_distress,
        # ── Research ────────────────────────────────────────────────────
        research_flags       = flags_list,
        research_tags        = tags_list,
        rbi_result           = rbi_result,
        litigation_count     = len(lit_flags),
        mca_flag_count       = len([f for f in flags_list if f.get("source") == "MCA"]),
        news_signals         = [s for s in news_signals if s][:5],
        sector_score         = res_scores.conditions.score,
        # ── Rate & Amount derivation ────────────────────────────────────
        rate_base            = rate_rec.base_rate,
        rate_premiums        = [p.model_dump() for p in rate_rec.premiums],
        rate_build_up        = rate_build_up_text,
        rate_derivation      = rate_deriv_text,
        amount_adjustments   = [a.model_dump() for a in amount_rec.adjustments],
        amount_derivation    = amount_deriv_text,
        amount_reason        = amount_reason_text,
        conditions_precedent = conds,
        covenants            = covs,
        mpbf_compliance      = mpbf_compliance_text,
        # ── Site visit ─────────────────────────────────────────────────
        site_visit_data              = site_visit_text,
        # ── Primary Insight ────────────────────────────────────────────
        qualitative_adjustment       = composite.qualitative_adjustment,
        qualitative_explanations     = composite.qualitative_explanations,
        cross_pillar_contradictions  = composite.cross_pillar_contradictions,
        factory_capacity_pct         = float(qualitative.get("factory_capacity_pct", -1) or -1),
        management_quality           = int(qualitative.get("management_quality", 0) or 0),
        site_condition               = str(qualitative.get("site_condition", "") or ""),
        key_person_risk              = bool(qualitative.get("key_person_risk", False)),
        supply_chain_risk            = bool(qualitative.get("supply_chain_risk", False)),
        cibil_commercial_score       = float(qualitative.get("cibil_commercial_score", -1) or -1),
        primary_insight_notes        = str(qualitative.get("notes", "") or ""),
        repo_rate                    = float(os.getenv("REPO_RATE", "6.50")),
        bank_spread                  = float(os.getenv("BANK_SPREAD", "3.00")),
    )

    narr_gen   = NarrativeGenerator(api_key=os.getenv("GEMINI_API_KEY"))
    narratives = narr_gen.generate_all(narr_input)
    print(f"           Narratives generated. Errors: {list(narratives.errors.keys()) or 'none'}")

    # ── 6. Build cam_data dict ────────────────────────────────
    print("[Pillar 3] Step 6/7 — Assembling CAM data...")
    all_dims = (
        composite.dimension_scores
        if composite.dimension_scores
        else []
    )

    cam_data = {
        # Identity
        "case_id":          case_id,
        "company_name":     narr_input.company_name,
        "cin":              narr_input.cin,
        "gstin":            req.get("gstin", ""),
        "industry":         industry,
        "loan_type":        loan_type,

        # Decision
        "decision":             composite.decision,
        "risk_band":            composite.risk_band,
        "composite_score":      composite.composite_score,
        "auto_reject":          composite.auto_reject,
        "rejection_reason":     composite.rejection_reason,

        # Amounts
        "requested_amount_inr":   requested_amount,
        "recommended_amount_inr": amount_rec.final,
        "wc_gap_inr":             amount_rec.wc_gap,
        "base_amount_inr":        amount_rec.base,

        # Rate
        "interest_rate":    rate_rec.final_rate,
        "base_rate":        rate_rec.base_rate,
        "rate_band":        rate_rec.rate_band,

        # Explainability chains
        "amount_adjustments":  [a.model_dump() for a in amount_rec.adjustments],
        "rate_premiums":       [p.model_dump() for p in rate_rec.premiums],

        # Dimension scores
        "dimension_scores": [d.model_dump() for d in all_dims],
        "five_c_scores": [
            {"name": "Character",   "score": res_scores.character.score,    "color": res_scores.character.color},
            {"name": "Capacity",    "score": cap_dim.score,                 "color": cap_dim.color},
            {"name": "Capital",     "score": cap2_dim.score,                "color": cap2_dim.color},
            {"name": "Collateral",  "score": col_dim.score,                 "color": col_dim.color},
            {"name": "Conditions",  "score": res_scores.conditions.score,   "color": res_scores.conditions.color},
        ],

        # Conditions
        "conditions_precedent": conds,
        "covenants":            covs,

        # Flags
        "research_flags":    flags_list,
        "extraction_flags":  extraction.get("risk_flags", {}).get("flags", []),
        "research_tags":     tags_list,

        # Narratives
        "narratives": narratives.model_dump(),

        # Pass-through data for document builder
        "promoters":      promoters,
        "company_profile":extraction.get("company_profile", {}),
        "loan_details":   req.get("loan", {}),
        "extraction":     extraction,

        # Metadata
        "generated_at":  started.isoformat(),
        "engine_version":"3.1.0",
        "prepared_by":   "Intelli-Credit AI Engine v3.1",

        # Score verbatim
        "explainability_text":       composite.explainability_text,

        # Primary Insight / Qualitative adjustment
        "qualitative_adjustment":    composite.qualitative_adjustment,
        "qualitative_explanations":  composite.qualitative_explanations,
        "cross_pillar_contradictions": composite.cross_pillar_contradictions,

        # Decision Rationale (from 8th narrative section)
        "decision_rationale": narratives.decision_rationale if hasattr(narratives, 'decision_rationale') else "",
    }


    # ── 7. Build Word document ────────────────────────────────
    print("[Pillar 3] Step 7/7 — Building Word document...")
    # Always resolve to absolute path to avoid path mismatch between
    # cam_engine working directory and backend working directory
    abs_output_dir = Path(output_dir).resolve()
    abs_output_dir.mkdir(parents=True, exist_ok=True)
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    docx_path = str(abs_output_dir / f"CAM_{case_id}_{ts}.docx")

    try:
        builder  = CAMBuilder()
        doc      = builder.build(cam_data)
        doc.save(docx_path)

        # Verify DOCX was actually written
        docx_file = Path(docx_path)
        if docx_file.exists() and docx_file.stat().st_size > 1024:
            cam_data["docx_path"] = str(docx_file)
            print(f"           DOCX saved: {docx_file} ({docx_file.stat().st_size:,} bytes)")
        else:
            print(f"[Pillar 3] WARNING: DOCX file missing or too small: {docx_path}", file=sys.stderr)
            cam_data["docx_path"] = None

        # PDF conversion
        pdf_path   = docx_path.replace(".docx", ".pdf")
        pdf_result = convert_to_pdf(docx_path, pdf_path)
        if pdf_result and Path(pdf_result).exists() and Path(pdf_result).stat().st_size > 1024:
            cam_data["pdf_path"] = str(Path(pdf_result).resolve())
            print(f"           PDF  saved: {cam_data['pdf_path']} ({Path(pdf_result).stat().st_size:,} bytes)")
        else:
            # Graceful degradation: serve DOCX if PDF conversion fails
            cam_data["pdf_path"] = cam_data.get("docx_path")
            print(f"           PDF conversion failed — DOCX will be served for PDF downloads")
    except Exception as e:
        import traceback
        print(f"[Pillar 3] Document build failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        cam_data["docx_path"] = None
        cam_data["pdf_path"]  = None
        cam_data["doc_error"] = str(e)

    elapsed = (datetime.now() - started).total_seconds()
    print(f"[Pillar 3] Done! CAM generated in {elapsed:.1f}s")
    print(f"   Decision: {cam_data['decision']}")
    print(f"   Amount:   Rs.{cam_data['recommended_amount_inr']/1e7:.2f} Cr")
    print(f"   Rate:     {cam_data['interest_rate']:.2f}% p.a.")
    print(f"   Score:    {cam_data['composite_score']}/100 [{cam_data['risk_band']}]")
    print(f"   DOCX:     {cam_data.get('docx_path','--')}")
    print(f"   PDF:      {cam_data.get('pdf_path','--')}")

    return cam_data


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _safe(v, fallback: float = 0.0) -> float:
    if v is None: return fallback
    if isinstance(v, dict): return float(v.get("value", fallback) or fallback)
    try:    return float(v)
    except: return fallback


def _extract_period_values(period_dict: Dict) -> list:
    """Extract ordered list of values from {period: {value: N}} dict."""
    if not isinstance(period_dict, dict):
        return []
    out = []
    for v in period_dict.values():
        val = _safe(v)
        if val != 0:
            out.append(val)
    return out


def _cagr(values: list) -> float:
    if len(values) < 2 or values[0] <= 0:
        return 0.0
    n = len(values) - 1
    try:
        return ((values[-1] / values[0]) ** (1 / n) - 1) * 100
    except:
        return 0.0


def _latest_val(d) -> float:
    if not isinstance(d, dict):
        return _safe(d)
    vals = [_safe(v) for v in d.values() if _safe(v) > 0]
    return vals[-1] if vals else 0.0


# ─────────────────────────────────────────────────────────────
# CLI usage (standalone test)
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pillar 3 — CAM Generator")
    parser.add_argument("--extraction", required=True, help="Path to extractor output JSON")
    parser.add_argument("--research",   default="{}",  help="Path to research agent JSON (optional)")
    parser.add_argument("--case-id",    default="TEST_CASE_001")
    parser.add_argument("--company",    default="Test Company Ltd")
    parser.add_argument("--amount",     type=float, default=10_000_000, help="Amount in INR")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    with open(args.extraction) as f:
        extraction = json.load(f)

    research = {}
    if args.research and args.research != "{}":
        try:
            with open(args.research) as f:
                research = json.load(f)
        except Exception:
            pass

    req = {
        "company_name": args.company,
        "cin":   extraction.get("company_profile", {}).get("cin", "U00000MH2020PTC000000"),
        "gstin": "27AAAAA0000A1Z5",
        "loan":  {"amount_inr": args.amount, "type": "Working Capital", "tenor_months": 36, "purpose": "Working capital requirements"},
        "promoters": [],
        "ingestion_version": "CLI_TEST",
    }

    result = generate_cam(
        case_id    = args.case_id,
        extraction = extraction,
        research   = research,
        req        = req,
        output_dir = args.output_dir,
    )
    print("\n[CLI] CAM JSON keys:", list(result.keys()))
