"""
cam_engine/narrative/models.py
================================
Pydantic models for the narrative generator.
NarrativeInput = everything Gemini needs for all 7 CAM sections.
CAMNarratives  = everything Gemini produces.

v2 upgrade: full CMA-grade fields per the SBI/HDFC CAM format.
"""

from __future__ import annotations

from typing import List, Optional, Any, Dict
from pydantic import BaseModel


class CAMNarratives(BaseModel):
    """All LLM-generated sections of the CAM."""
    executive_summary:  str = ""
    character:          str = ""
    capacity:           str = ""
    capital:            str = ""
    collateral:         str = ""
    conditions:         str = ""
    risk_mitigants:     str = ""
    recommendation:     str = ""
    decision_rationale: str = ""   # cross-pillar AI explainability

    # track which sections had errors
    errors: Dict[str, str] = {}


class NarrativeInput(BaseModel):
    """Fully hydrated input bundle passed to the narrative generator.

    v2: Extended with full CMA-grade 3-year income statement, balance sheet,
        MPBF (Tandon), DSCR computation, GST reconciliation, and capital fields.
    """

    # ── Identity ─────────────────────────────────────────────
    case_id:        str
    company_name:   str
    cin:            str
    industry:       str
    loan_type:      str
    tenor_months:   int
    requested_cr:   float
    recommended_cr: float

    # ── Promoters ─────────────────────────────────────────────
    promoters: List[Dict[str, Any]] = []

    # ── Decision ──────────────────────────────────────────────
    decision:        str
    risk_band:       str
    composite_score: int
    interest_rate:   float

    # ── Dimension scores ──────────────────────────────────────
    character_score:  int
    capacity_score:   int
    capital_score:    int
    collateral_score: int
    conditions_score: int

    # ── Score breakdowns (explainability) ─────────────────────
    capacity_breakdown:   List[Dict[str, Any]] = []
    capital_breakdown:    List[Dict[str, Any]] = []
    collateral_breakdown: List[Dict[str, Any]] = []

    # ── 3-year income statement (lacs / crores as extracted) ──
    revenue:  List[float] = []    # FY1, FY2, FY3  (net sales in crores)
    ebitda:   List[float] = []
    pat:      List[float] = []
    cfo:      List[float] = []
    periods:  List[str]   = []    # ["FY22", "FY23", "FY24"]
    rev_cagr: float = 0.0
    ebitda_margin_latest: float = 0.0

    # ── Gross profit (extracted or derived from revenue - cost) ─
    gross_profit:    List[float] = []    # FY1, FY2, FY3

    # ── Finance charges (term loan + CC, per year) ───────────
    finance_charges: List[float] = []   # FY1, FY2, FY3

    # ── Depreciation (latest year, for DSCR) ─────────────────
    depreciation_latest: float = 0.0

    # ── 3-year balance sheet ──────────────────────────────────
    net_worth_series:   List[float] = []   # FY1, FY2, FY3 (crores)
    total_debt_series:  List[float] = []
    current_ratio_series: List[float] = []
    de_ratio_series:    List[float] = []

    # Net Worth (latest), used for backward compat
    net_worth_cr:      float = 0.0
    total_debt_cr:     float = 0.0
    tangible_nw_cr:    float = 0.0
    total_assets_cr:   float = 0.0
    de_ratio:          float = 0.0

    # ── Capital structure (lacs) ──────────────────────────────
    share_capital_series:    List[float] = []   # FY1, FY2, FY3
    reserves_surplus_series: List[float] = []
    tol_series:              List[float] = []   # Total Outside Liabilities
    tnw_series:              List[float] = []   # Tangible NW
    tol_tnw_series:          List[float] = []   # TOL/TNW ratio
    term_loan_series:        List[float] = []
    cc_outstanding_series:   List[float] = []
    unsecured_loans:         float = 0.0        # promoter unsecured loans (lacs)

    # ── Working capital / MPBF (Tandon Method II) ─────────────
    total_current_assets:    float = 0.0   # lacs
    current_liab_ex_bank:    float = 0.0   # excludes bank borrowings
    wc_gap:                  float = 0.0   # TCA - CL_ex_bank
    proposed_cc:             float = 0.0   # proposed CC limit
    mpbf:                    float = 0.0   # max permissible bank finance
    nwc:                     float = 0.0   # Net Working Capital
    min_nwc_stipulated:      float = 0.0   # 25% of WC gap
    within_mpbf:             str   = "Yes"
    within_mpbf_margin:      str   = "adequate NWC margin from own sources"

    # ── DSCR components (latest actual year) ─────────────────
    tl_repayment_latest: float = 0.0    # term loan repayment (lacs)
    cash_accrual:        float = 0.0    # PAT + Dep + FC
    debt_service:        float = 0.0    # TL repayment + FC
    dscr:                float = 0.0
    icr:                 float = 0.0

    # ── Key ratios ────────────────────────────────────────────
    promoter_shareholding: float = 0.0
    cfo_pat_ratio:         float = 0.0

    # ── Collateral ────────────────────────────────────────────
    collateral_assets:   List[Dict[str, Any]] = []
    total_market_cr:     float = 0.0
    total_distress_cr:   float = 0.0
    coverage_market:     float = 0.0
    coverage_distress:   float = 0.0
    guarantors_text:     str   = "Personal guarantee of all promoters."

    # ── Existing credit facilities ────────────────────────────
    existing_facilities: List[Dict[str, Any]] = []  # [{lender, type, sanctioned, outstanding, rate}]

    # ── Research agent outputs ────────────────────────────────
    research_flags:   List[Dict[str, Any]] = []
    research_tags:    List[str]  = []
    rbi_result:       str = "Not flagged in RBI Wilful Defaulter database"
    litigation_count: int = 0
    mca_flag_count:   int = 0
    news_signals:     List[str] = []
    sector_score:     int = 70
    gstn_status:      str = "Active"

    # ── GST reconciliation data ───────────────────────────────
    gst_compliance_pct:  float = 100.0
    gst_turnover:        float = 0.0    # declared GST turnover (lacs)
    bank_credits:        float = 0.0    # actual bank credits (lacs)
    gst_bank_ratio:      float = 0.0    # gst_turnover / bank_credits
    gstr2a_itc:          float = 0.0    # auto-populated ITC (lacs)
    gstr3b_itc:          float = 0.0    # self-declared ITC (lacs)
    itc_variance_pct:    float = 0.0    # (3B - 2A) / 2A * 100

    # ── Rate derivation ───────────────────────────────────────
    rate_base:      float = 9.50
    rate_premiums:  List[Dict[str, Any]] = []
    rate_build_up:  str = ""   # human-readable string, e.g. "9.50% + 0.75% + 0.25% = 10.50%"
    rate_derivation: str = ""  # full multi-line derivation

    # ── Amount derivation ─────────────────────────────────────
    amount_adjustments: List[Dict[str, Any]] = []
    amount_derivation:  str = ""   # full step-by-step derivation text
    amount_reason:      str = ""

    # ── Conditions and covenants ──────────────────────────────
    conditions_precedent: List[str] = []
    covenants:            List[str] = []
    mpbf_compliance:      str = ""

    # ── Site visit data ───────────────────────────────────────
    site_visit_data: str = ""

    # ── Repo rate context ─────────────────────────────────────
    repo_rate:   float = 6.50
    bank_spread: float = 3.00

    # ── Primary Insight (Qualitative) ─────────────────────────
    qualitative_adjustment:      int   = 0
    qualitative_explanations:    list  = []
    cross_pillar_contradictions: list  = []
    factory_capacity_pct:        float = -1.0
    management_quality:          int   = 0
    site_condition:              str   = ""
    key_person_risk:             bool  = False
    supply_chain_risk:           bool  = False
    cibil_commercial_score:      float = -1.0
    primary_insight_notes:       str   = ""
