"""
output/builder.py
Assembles the final structured JSON from all pipeline stages.
This is the definitive output format — every field has source + confidence tag.

Output sections:
    1.  extraction_metadata     — pipeline run info
    2.  company_profile         — identity, CIN, promoter
    3.  income_statement        — revenue, EBITDA, PAT across periods
    4.  balance_sheet           — debt, cash, gearing
    5.  credit_metrics          — ICR, DSCR, facilities
    6.  operational_metrics     — products, capacity, customers
    7.  audit_and_compliance    — qualifications, contingent liabilities
    8.  risk_flags              — all flags with severity
    9.  cross_validation        — all 10 check results
    10. early_warning_signals   — top critical alerts
    11. extraction_gaps         — fields not found, docs missing
    12. credit_recommendation   — APPROVE / REJECT / REFER decision
"""

from datetime import datetime


def build_final_json(
    raw_texts:    list,
    structured:   dict,
    validation:   list,
    source_file:  str,
    company_hint: str,
) -> dict:
    """
    Assembles the complete credit extraction JSON output.

    Args:
        raw_texts    : pages from extractor (list of dicts)
        structured   : LLM output (dict with 'fields' key)
        validation   : cross-validator results (list of check dicts)
        source_file  : original file path or "DEMO"
        company_hint : company name hint passed by user

    Returns:
        Complete dict — the final JSON saved to disk
    """
    fields     = structured.get("fields", structured)
    risk_flags = _compute_risk_flags(fields, validation)
    decision   = _compute_decision(risk_flags)
    ews        = _compute_early_warnings(validation, fields)

    return {
        # ── 1. PIPELINE METADATA ──────────────────────────────
        "extraction_metadata": {
            "engine_version":   "1.0.0",
            "extracted_at":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_file":      source_file,
            "company_hint":     company_hint or "Unknown",
            "pages_processed":  len(raw_texts),
            "extractor_types":  list(set(p.get("type", "?") for p in raw_texts)),
            "parse_success":    structured.get("parse_success", True),
            "llm_provider":     structured.get("provider", "demo"),
        },

        # ── 2. COMPANY PROFILE ────────────────────────────────
        "company_profile": _extract_section(fields, "company_profile", {
            "legal_name":         ("Unknown", "LOW"),
            "cin":                ("Not found", "LOW"),
            "sector":             ("Unknown", "LOW"),
            "incorporation_year": (None, "LOW"),
            "registered_address": ("Not found", "LOW"),
            "promoter_name":      ("Not found", "LOW"),
            "promoter_stake_pct": (None, "LOW"),
        }),

        # ── 3. INCOME STATEMENT ───────────────────────────────
        "income_statement": fields.get("income_statement", {
            "_note": "Not extracted — document may not contain P&L data"
        }),

        # ── 4. BALANCE SHEET ──────────────────────────────────
        "balance_sheet": fields.get("balance_sheet", {
            "_note": "Not extracted — document may not contain balance sheet data"
        }),

        # ── 5. CREDIT METRICS ─────────────────────────────────
        "credit_metrics": fields.get("credit_metrics", {
            "_note": "Not extracted — upload financial statements"
        }),

        # ── 6. OPERATIONAL METRICS ────────────────────────────
        "operational_metrics": fields.get("operational_metrics", {
            "_note": "Not extracted — upload annual report or MD&A section"
        }),

        # ── 7. AUDIT & COMPLIANCE ─────────────────────────────
        "audit_and_compliance": {
            "audit_qualifications":   fields.get("audit_qualifications", []),
            "contingent_liabilities": fields.get("contingent_liabilities", []),
            "qualification_count":    len(fields.get("audit_qualifications", [])),
        },

        # ── 8. RISK FLAGS ─────────────────────────────────────
        "risk_flags": {
            "total":    risk_flags["total"],
            "CRITICAL": risk_flags["CRITICAL"],
            "HIGH":     risk_flags["HIGH"],
            "MEDIUM":   risk_flags["MEDIUM"],
            "LOW":      risk_flags["LOW"],
            "flags":    risk_flags["all_flags"],
        },

        # ── 9. CROSS-VALIDATION ───────────────────────────────
        "cross_validation": {
            "checks_run":    len(validation),
            "checks_passed": sum(
                1 for c in validation if "PASS" in c.get("result", "")
            ),
            "checks_failed": sum(
                1 for c in validation
                if any(kw in c.get("result", "") for kw in ["FAIL", "FLAG", "CRITICAL"])
            ),
            "checks": validation,
        },

        # ── 10. EARLY WARNING SIGNALS ─────────────────────────
        "early_warning_signals": ews,

        # ── 11. EXTRACTION GAPS ───────────────────────────────
        "extraction_gaps": {
            "fields_not_found": fields.get("fields_not_found", []),
            "note": (
                "Upload additional documents to fill gaps. "
                "GST returns + bank statements unlock fraud detection checks CV_009 and CV_010."
            ),
        },

        # ── 12. CREDIT RECOMMENDATION ────────────────────────
        "credit_recommendation": decision,
    }


# ─────────────────────────────────────────────────────────────
# Internal helper functions
# ─────────────────────────────────────────────────────────────

def _extract_section(fields: dict, section: str, defaults: dict) -> dict:
    """
    Merges extracted section with defaults for any missing fields.
    If a field was extracted, use it. If not, use default + mark as not found.
    """
    extracted = fields.get(section, {})
    result    = {}
    for key, (default_val, default_conf) in defaults.items():
        val = extracted.get(key)
        if val not in (None, "", "Not found", "Unknown"):
            result[key] = val
        else:
            result[key] = {
                "value":      default_val,
                "confidence": default_conf,
                "note":       "Not found in uploaded documents",
            }
    return result


def _compute_risk_flags(fields: dict, validation: list) -> dict:
    """
    Combines risk flags from two sources:
        1. LLM-detected red flags from document narrative
        2. Cross-validation check failures
    Returns aggregated dict with counts by severity.
    """
    all_flags = []

    # Source 1: LLM-extracted narrative red flags (default severity: MEDIUM)
    for flag in fields.get("red_flags_found", []):
        all_flags.append({
            "source":   "LLM_EXTRACTION",
            "severity": "MEDIUM",
            "flag":     flag if isinstance(flag, str) else str(flag),
        })

    # Source 2: Cross-validation failures
    for check in validation:
        result = check.get("result", "")
        sev    = check.get("severity", "LOW")
        if any(kw in result for kw in ["FAIL", "FLAG", "WARN", "CRITICAL"]):
            all_flags.append({
                "source":      "CROSS_VALIDATION",
                "check_id":    check.get("check_id"),
                "severity":    sev,
                "flag":        result,
                "description": check.get("description"),
            })

    # Count by severity
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in all_flags:
        sev = f.get("severity", "LOW")
        if sev in counts:
            counts[sev] += 1

    return {
        "total":     len(all_flags),
        "all_flags": all_flags,
        **counts,
    }


def _compute_decision(risk_flags: dict) -> dict:
    """
    Rule-based decision tree — deterministic and auditable.

    Decision rules:
        Any CRITICAL flag   → REJECT / HOLD
        3+ HIGH flags       → REFER TO CREDIT COMMITTEE
        1-2 HIGH flags      → CONDITIONAL APPROVAL
        0 flags             → RECOMMEND APPROVAL
        Only MEDIUM/LOW     → APPROVE WITH MONITORING
    """
    critical = risk_flags["CRITICAL"]
    high     = risk_flags["HIGH"]
    total    = risk_flags["total"]

    if critical > 0:
        decision   = "REJECT / HOLD"
        rationale  = (
            f"{critical} CRITICAL flag(s) detected. "
            f"Cannot proceed with lending until all critical issues are resolved."
        )
        risk_level = "CRITICAL"

    elif high >= 3:
        decision   = "REFER TO CREDIT COMMITTEE"
        rationale  = (
            f"{high} HIGH severity flags detected. "
            f"Requires senior credit committee review before any sanction."
        )
        risk_level = "HIGH"

    elif high >= 1:
        decision   = "CONDITIONAL APPROVAL"
        rationale  = (
            f"{high} HIGH flag(s) noted. "
            f"Approval possible with enhanced covenants and monitoring conditions."
        )
        risk_level = "MEDIUM"

    elif total == 0:
        decision   = "RECOMMEND APPROVAL"
        rationale  = "No risk flags detected across all checks. Standard terms applicable."
        risk_level = "LOW"

    else:
        decision   = "APPROVE WITH MONITORING"
        rationale  = (
            f"{total} minor flag(s) detected. "
            f"Standard approval with quarterly covenant monitoring."
        )
        risk_level = "LOW"

    return {
        "decision":    decision,
        "risk_level":  risk_level,
        "rationale":   rationale,
        "conditions":  _generate_conditions(risk_flags),
        "confidence":  "HIGH" if risk_flags["total"] > 0 else "MEDIUM",
        "disclaimer":  (
            "Preliminary automated assessment only. "
            "Full CAM memo, site visit, and credit committee approval "
            "required before final sanction."
        ),
    }


def _generate_conditions(risk_flags: dict) -> list:
    """Generates specific lending conditions based on detected flag severity."""
    conditions = []
    if risk_flags["CRITICAL"] > 0:
        conditions.append("Resolve all CRITICAL flags before any disbursement")
        conditions.append("Obtain legal clearance certificate")
    if risk_flags["HIGH"] > 0:
        conditions.append("Obtain satisfactory written explanation for all HIGH severity flags")
        conditions.append("Additional collateral security — minimum 1.5x coverage")
    if risk_flags["MEDIUM"] > 0:
        conditions.append("Quarterly financial statement submission mandatory")
        conditions.append("Annual factory / office site visit by credit officer")
    if not conditions:
        conditions.append("Standard KYC documentation and legal search")
        conditions.append("Sanction within standard terms and conditions")
    return conditions


def _compute_early_warnings(validation: list, fields: dict) -> dict:
    """
    Identifies the top early warning signals from validation results.
    These are the alerts that need IMMEDIATE attention.
    """
    warnings = []

    # From cross-validation: only CRITICAL and HIGH that actually failed
    for check in validation:
        sev    = check.get("severity", "LOW")
        result = check.get("result", "")
        if sev in ("CRITICAL", "HIGH") and any(
            kw in result for kw in ["FLAG", "FAIL", "CRITICAL"]
        ):
            warnings.append({
                "signal":             check.get("description", "Unknown"),
                "severity":           sev,
                "detail":             result,
                "recommended_action": _get_action(sev),
            })

    # From LLM extraction: fraud-specific keywords trigger CRITICAL EWS
    for flag in fields.get("red_flags_found", []):
        flag_str = str(flag).lower()
        if any(kw in flag_str for kw in [
            "circular", "fraud", "divert", "fake", "fabricat",
            "shell", "liquidat", "winding up", "insolvency"
        ]):
            warnings.append({
                "signal":             "Potential fraud / insolvency indicator detected in document",
                "severity":           "CRITICAL",
                "detail":             str(flag),
                "recommended_action": "Immediately escalate to risk and fraud team. Halt processing.",
            })

    return {
        "triggered":     len(warnings) > 0,
        "warning_count": len(warnings),
        "warnings":      warnings,
    }


def _get_action(severity: str) -> str:
    """Returns recommended action string for a given severity level."""
    actions = {
        "CRITICAL": "Halt processing immediately. Escalate to senior credit officer.",
        "HIGH":     "Request written clarification from borrower. Obtain third-party verification.",
        "MEDIUM":   "Document risk in credit file. Apply additional loan covenants.",
        "LOW":      "Note in credit file. Monitor on quarterly basis.",
    }
    return actions.get(severity, "Review and monitor.")