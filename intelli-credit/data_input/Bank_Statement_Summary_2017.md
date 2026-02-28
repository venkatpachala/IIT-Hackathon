# BANK STATEMENT EXPORT & ANALYST SUMMARY
**Source System:** FinSight Extract (Core Banking Integration)
**Customer Name:** Bhushan Steel Limited
**Account No:** 0012985743001
**Branch:** State Bank of India - Corporate Accounts Group (CAG), New Delhi
**Statement Period:** 01-APR-2017 to 30-SEP-2017
**Currency:** INR

---

## 1. Automated Transaction Analaysis
**Total Credits (Inflow):** ₹ 8,421.50 Crore
**Total Debits (Outflow):** ₹ 8,642.10 Crore
**Average Daily Balance (ADB):** ₹ 115.30 Crore (Warning: -18% vs Previous Half-Year)

### Identified Red Flags (Alerts Threshold: High)
1. **High Volume Circular Transfers:** 
   *    Alert: Apparent "round-tripping" detected. Multiple high-value transfers (aggregating ₹2,100 Cr) between BSL and "Bhushan Energy Ltd" followed by corresponding receipts within 48 hours.
2. **Missing LC/BG Backing:**
   *    Alert: Payments to suppliers (e.g., "Vishal Ispat Ltd") totaling ₹ 450 Cr lack corresponding Bill of Lading (BoL) or LC tracking numbers.
3. **Cheque/ECS Return (Bounces):**
   *    Alert: 3 instances of "Insufficient Funds" observed in August 2017 for outward ECS mandates to minor creditors.
4. **Loan Service Delays:**
   *    Alert: Monthly interest servicing to PNB & SBI delayed by an average of 8 days across June, July, and August 2017.

---

## 2. Sample High-Value Transactions Ledger

| Date | Transaction Particulars (Narration) | Ref / Chq No. | Debit (₹ Cr) | Credit (₹ Cr) | Running Balance (₹ Cr) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **01-Apr-17** | **B/F Opening Balance** | - | - | - | **412.50** |
| 03-Apr-17 | NEFT: Maruti Suzuki India Ltd (Receivable) | MSIL/Q1/899 | | 150.00 | 562.50 |
| 05-Apr-17 | RTGS: Bhushan Energy Ltd (ICD Transfer) | RTGS/BEL/0405 | 250.00 | | 312.50 |
| 10-Apr-17 | CLG: Vishal Ispat Ltd (Raw Material) | 499211 | 185.20 | | 127.30 |
| ... | *[1,420 normal operational entries collapsed]* | ... | ... | ... | ... |
| 14-Aug-17 | **ECS: PNB Interest Recovery (JUL)** | PNB/ECS/08 | 45.50 | | 84.80 |
| 18-Aug-17 | RTGS: Bhushan Energy Ltd (ICD Returned) | RTGS/BSL/0818 | | 245.00 | 329.80 |
| 25-Aug-17 | **CHQ RTN: JSPL Ltd (Insufficient Funds)** | 499388 | **(Failed)** | | 329.80 |
| 28-Aug-17 | **CHQ RTN: JSPL Ltd (Insufficient Funds)** | 499388 | **(Failed)** | | 329.80 |
| 05-Sep-17 | NEFT: Tata Motors Ltd (Receivable) | TML/Q2/102 | | 400.00 | 729.80 |
| 12-Sep-17 | RTGS: Transfer to Promoter Account (Singal) | RTGS/DIR/0912 | 150.00 | | 579.80 |
| **30-Sep-17** | **CLOSING BALANCE** | - | - | - | **191.90** |

---
*End of Extract. Exported via Secure API Integration.*
