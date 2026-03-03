'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import Sidebar from '../../components/Sidebar';
import styles from './CreateCase.module.css';

/* ─── Types ─── */
interface Promoter {
    fullName: string;
    din: string;
    pan: string;
    designation: string;
    shareholding: string;
}

interface CompanyDetails {
    legalName: string;
    cin: string;
    gstin: string;
    pan: string;
    industry: string;
    constitution: string;
    incorporationDate: string;
    address: string;
    city: string;
    state: string;
    pincode: string;
}

interface LoanDetails {
    amount: string;
    loanType: string;
    tenor: string;
    purpose: string;
    observations: string;
    siteVisit: boolean;
    visitDate: string;
    plantCondition: number;
    capacityUtilization: string;
    mgmtTransparency: number;
}

const INDUSTRIES = [
    'Textile Manufacturing', 'Pharmaceutical', 'Infrastructure', 'NBFC / Finance',
    'Steel & Metal', 'Food Processing', 'IT / Technology', 'Real Estate', 'Chemicals', 'Other',
];

const STATES = [
    'Andhra Pradesh', 'Gujarat', 'Karnataka', 'Maharashtra', 'Rajasthan',
    'Tamil Nadu', 'Telangana', 'Uttar Pradesh', 'West Bengal', 'Other',
];

const CONSTITUTIONS = ['Private Limited', 'Public Limited', 'LLP', 'Partnership', 'Proprietorship', 'OPC'];
const DESIGNATIONS = ['Managing Director', 'Director', 'CEO', 'COO', 'CFO', 'Partner', 'Proprietor'];
const LOAN_TYPES = ['Working Capital', 'Term Loan', 'LAP (Loan Against Property)', 'Project Finance'];

function StarRating({ value, onChange, max = 5 }: { value: number; onChange: (n: number) => void; max?: number }) {
    return (
        <div className={styles.starRow}>
            {Array.from({ length: max }, (_, i) => i + 1).map((star) => (
                <button
                    key={star}
                    type="button"
                    className={`${styles.star} ${star <= value ? styles.starFilled : ''}`}
                    onClick={() => onChange(star)}
                >
                    ★
                </button>
            ))}
            <span className={styles.starValue}>{value}/{max}</span>
        </div>
    );
}

export default function CreateCasePage() {
    const router = useRouter();
    const [tab, setTab] = useState(0);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const [company, setCompany] = useState<CompanyDetails>({
        legalName: '', cin: '', gstin: '', pan: '', industry: '',
        constitution: '', incorporationDate: '', address: '', city: '', state: '', pincode: '',
    });

    const [promoters, setPromoters] = useState<Promoter[]>([
        { fullName: '', din: '', pan: '', designation: '', shareholding: '' },
    ]);

    const [loan, setLoan] = useState<LoanDetails>({
        amount: '', loanType: 'Working Capital', tenor: '', purpose: '', observations: '',
        siteVisit: true, visitDate: '', plantCondition: 4, capacityUtilization: '', mgmtTransparency: 4,
    });

    /* Promoter helpers */
    const addPromoter = () => setPromoters((p) => [...p, { fullName: '', din: '', pan: '', designation: '', shareholding: '' }]);
    const removePromoter = (i: number) => setPromoters((p) => p.filter((_, idx) => idx !== i));
    const updatePromoter = (i: number, field: keyof Promoter, val: string) =>
        setPromoters((p) => p.map((pr, idx) => idx === i ? { ...pr, [field]: val } : pr));

    const handleSubmit = async () => {
        setSubmitting(true);
        setError('');
        try {
            const token = localStorage.getItem('access_token');
            const payload = { company, promoters, loan };
            const res = await fetch('http://localhost:8000/cases', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                body: JSON.stringify(payload),
            });

            if (res.ok) {
                const data = await res.json();
                router.push(`/cases/${data.case_id}/upload`);
            } else {
                // Demo mode: generate a fake case ID and redirect
                const fakeId = `CASE_2026_${String(Math.floor(Math.random() * 900) + 100)}`;
                router.push(`/cases/${fakeId}/upload`);
            }
        } catch {
            const fakeId = `CASE_2026_${String(Math.floor(Math.random() * 900) + 100)}`;
            router.push(`/cases/${fakeId}/upload`);
        } finally {
            setSubmitting(false);
        }
    };

    const tabs = ['Company Details', 'Promoters', 'Loan Request'];

    return (
        <div className={styles.layout}>
            <Sidebar role="manager" activePage="/cases/new" />

            <main className={styles.main}>
                {/* Header */}
                <div className={styles.pageHeader}>
                    <Link href="/dashboard/manager" className={styles.backLink}>← Back</Link>
                    <h1 className={styles.pageTitle}>New Credit Application</h1>
                </div>

                {/* Tab progress bar */}
                <div className={styles.tabNav}>
                    {tabs.map((t, i) => (
                        <button
                            key={t}
                            id={`tab-${i}`}
                            className={`${styles.tabBtn} ${tab === i ? styles.tabActive : ''} ${i < tab ? styles.tabDone : ''}`}
                            onClick={() => { if (i < tab) setTab(i); }}
                            type="button"
                        >
                            <span className={styles.tabNum}>{i < tab ? '✓' : i + 1}</span>
                            <span className={styles.tabLabel}>{t}</span>
                        </button>
                    ))}
                    <div className={styles.progressTrack}>
                        <div className={styles.progressFill} style={{ width: `${(tab / (tabs.length - 1)) * 100}%` }} />
                    </div>
                </div>

                {/* ─── TAB 1: Company Details ─── */}
                {tab === 0 && (
                    <div className={`${styles.tabContent} animate-fade-in`}>
                        <div className={styles.sectionTitle}>Company Details</div>

                        <div className={styles.formGrid}>
                            <div className={`form-group ${styles.fullWidth}`}>
                                <label className="form-label">Legal Company Name *</label>
                                <input className="form-input" placeholder="Shree Ram Textiles Private Limited"
                                    value={company.legalName} onChange={(e) => setCompany({ ...company, legalName: e.target.value })} />
                            </div>

                            <div className="form-group">
                                <label className="form-label">CIN *</label>
                                <input className="form-input" placeholder="U17100MH2010PTC123456" maxLength={21}
                                    value={company.cin} onChange={(e) => setCompany({ ...company, cin: e.target.value })} />
                                <span className="form-hint">ℹ️ 21 characters — starts with L or U</span>
                            </div>

                            <div className="form-group">
                                <label className="form-label">GSTIN *</label>
                                <input className="form-input" placeholder="27AAACS1234A1Z5" maxLength={15}
                                    value={company.gstin} onChange={(e) => setCompany({ ...company, gstin: e.target.value })} />
                                <span className="form-hint">ℹ️ 15 characters</span>
                            </div>

                            <div className="form-group">
                                <label className="form-label">PAN (Company)</label>
                                <input className="form-input" placeholder="AAACS1234A" maxLength={10}
                                    value={company.pan} onChange={(e) => setCompany({ ...company, pan: e.target.value })} />
                            </div>

                            <div className="form-group">
                                <label className="form-label">Industry / Sector</label>
                                <select className="form-input" value={company.industry}
                                    onChange={(e) => setCompany({ ...company, industry: e.target.value })}>
                                    <option value="">Select industry…</option>
                                    {INDUSTRIES.map((i) => <option key={i} value={i}>{i}</option>)}
                                </select>
                            </div>

                            <div className="form-group">
                                <label className="form-label">Constitution Type</label>
                                <select className="form-input" value={company.constitution}
                                    onChange={(e) => setCompany({ ...company, constitution: e.target.value })}>
                                    <option value="">Select type…</option>
                                    {CONSTITUTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
                                </select>
                            </div>

                            <div className="form-group">
                                <label className="form-label">Date of Incorporation</label>
                                <input className="form-input" type="date"
                                    value={company.incorporationDate} onChange={(e) => setCompany({ ...company, incorporationDate: e.target.value })} />
                            </div>
                        </div>

                        <div className={styles.subSectionTitle}>Registered Address</div>
                        <div className={styles.formGrid}>
                            <div className={`form-group ${styles.fullWidth}`}>
                                <label className="form-label">Street Address</label>
                                <input className="form-input" placeholder="Plot 45, GIDC Estate, Phase 2"
                                    value={company.address} onChange={(e) => setCompany({ ...company, address: e.target.value })} />
                            </div>
                            <div className="form-group">
                                <label className="form-label">City</label>
                                <input className="form-input" placeholder="Surat"
                                    value={company.city} onChange={(e) => setCompany({ ...company, city: e.target.value })} />
                            </div>
                            <div className="form-group">
                                <label className="form-label">State</label>
                                <select className="form-input" value={company.state}
                                    onChange={(e) => setCompany({ ...company, state: e.target.value })}>
                                    <option value="">Select state…</option>
                                    {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                                </select>
                            </div>
                            <div className="form-group">
                                <label className="form-label">Pincode</label>
                                <input className="form-input" placeholder="395010" maxLength={6}
                                    value={company.pincode} onChange={(e) => setCompany({ ...company, pincode: e.target.value })} />
                            </div>
                        </div>

                        <div className={styles.tabActions}>
                            <div />
                            <button className="btn-primary" id="btn-next-promoters" onClick={() => setTab(1)}>
                                Next: Promoters →
                            </button>
                        </div>
                    </div>
                )}

                {/* ─── TAB 2: Promoters ─── */}
                {tab === 1 && (
                    <div className={`${styles.tabContent} animate-fade-in`}>
                        <div className={styles.sectionTitle}>Promoters / Directors</div>

                        {promoters.map((pr, i) => (
                            <div key={i} className={styles.promoterCard}>
                                <div className={styles.promoterHeader}>
                                    <span className={styles.promoterLabel}>Promoter {i + 1}</span>
                                    {promoters.length > 1 && (
                                        <button type="button" className={styles.removeBtn} onClick={() => removePromoter(i)}>
                                            Remove
                                        </button>
                                    )}
                                </div>
                                <div className={styles.formGrid}>
                                    <div className={`form-group ${styles.fullWidth}`}>
                                        <label className="form-label">Full Name *</label>
                                        <input className="form-input" placeholder="Ramesh Kumar Agarwal"
                                            value={pr.fullName} onChange={(e) => updatePromoter(i, 'fullName', e.target.value)} />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">DIN</label>
                                        <input className="form-input" placeholder="01234567" maxLength={8}
                                            value={pr.din} onChange={(e) => updatePromoter(i, 'din', e.target.value)} />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">PAN</label>
                                        <input className="form-input" placeholder="AAAPA1234B" maxLength={10}
                                            value={pr.pan} onChange={(e) => updatePromoter(i, 'pan', e.target.value)} />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">Designation</label>
                                        <select className="form-input" value={pr.designation}
                                            onChange={(e) => updatePromoter(i, 'designation', e.target.value)}>
                                            <option value="">Select…</option>
                                            {DESIGNATIONS.map((d) => <option key={d} value={d}>{d}</option>)}
                                        </select>
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">Shareholding %</label>
                                        <input className="form-input" placeholder="55" type="number" min="0" max="100"
                                            value={pr.shareholding} onChange={(e) => updatePromoter(i, 'shareholding', e.target.value)} />
                                    </div>
                                </div>
                            </div>
                        ))}

                        <button type="button" className={styles.addPromoterBtn} id="btn-add-promoter" onClick={addPromoter}>
                            + Add Another Promoter
                        </button>

                        <div className={styles.tabActions}>
                            <button className="btn-secondary" onClick={() => setTab(0)}>← Back</button>
                            <button className="btn-primary" id="btn-next-loan" onClick={() => setTab(2)}>
                                Next: Loan Request →
                            </button>
                        </div>
                    </div>
                )}

                {/* ─── TAB 3: Loan Request ─── */}
                {tab === 2 && (
                    <div className={`${styles.tabContent} animate-fade-in`}>
                        <div className={styles.sectionTitle}>Loan Request</div>

                        <div className={styles.formGrid}>
                            <div className="form-group">
                                <label className="form-label">Loan Amount Requested (₹) *</label>
                                <input className="form-input" placeholder="1,00,00,000"
                                    value={loan.amount} onChange={(e) => setLoan({ ...loan, amount: e.target.value })} />
                                <span className="form-hint">ℹ️ Enter in absolute INR (e.g. 10000000 for ₹1 Cr)</span>
                            </div>

                            <div className="form-group">
                                <label className="form-label">Tenor (Months) *</label>
                                <input className="form-input" type="number" placeholder="36"
                                    value={loan.tenor} onChange={(e) => setLoan({ ...loan, tenor: e.target.value })} />
                            </div>
                        </div>

                        <div className="form-group" style={{ marginBottom: 20 }}>
                            <label className="form-label">Loan Type *</label>
                            <div className={styles.radioGrid}>
                                {LOAN_TYPES.map((t) => (
                                    <label key={t} className={`${styles.radioCard} ${loan.loanType === t ? styles.radioCardActive : ''}`}>
                                        <input type="radio" name="loanType" value={t} checked={loan.loanType === t}
                                            onChange={(e) => setLoan({ ...loan, loanType: e.target.value })} />
                                        <span>{t}</span>
                                    </label>
                                ))}
                            </div>
                        </div>

                        <div className="form-group" style={{ marginBottom: 24 }}>
                            <label className="form-label">Purpose of Loan *</label>
                            <textarea className="form-input" placeholder="Working capital expansion for raw material procurement and seasonal inventory build-up…"
                                rows={3} value={loan.purpose} onChange={(e) => setLoan({ ...loan, purpose: e.target.value })} />
                        </div>

                        {/* Qualitative Notes */}
                        <div className={styles.qualSection}>
                            <div className={styles.qualSectionTitle}>Qualitative Notes <span className={styles.optional}>(Optional)</span></div>
                            <div className={styles.qualNote}>These notes will be analysed by AI and factored into the risk score.</div>

                            <div className="form-group" style={{ marginBottom: 20 }}>
                                <label className="form-label">Credit Officer Observations</label>
                                <textarea className="form-input" rows={4}
                                    placeholder="Factory visited on 12-Jan-2026. Plant operating at 72% capacity. Strong order book visible. MD was transparent and cooperative during visit…"
                                    value={loan.observations} onChange={(e) => setLoan({ ...loan, observations: e.target.value })} />
                            </div>

                            <div className={styles.visitGrid}>
                                <div className="form-group">
                                    <label className="form-label">Site Visit Conducted?</label>
                                    <div className={styles.toggleRow}>
                                        {[true, false].map((val) => (
                                            <label key={String(val)} className={`${styles.toggleOpt} ${loan.siteVisit === val ? styles.toggleActive : ''}`}>
                                                <input type="radio" checked={loan.siteVisit === val}
                                                    onChange={() => setLoan({ ...loan, siteVisit: val })} />
                                                {val ? '● Yes' : '○ No'}
                                            </label>
                                        ))}
                                    </div>
                                </div>

                                {loan.siteVisit && (
                                    <div className="form-group">
                                        <label className="form-label">Visit Date</label>
                                        <input className="form-input" type="date" value={loan.visitDate}
                                            onChange={(e) => setLoan({ ...loan, visitDate: e.target.value })} />
                                    </div>
                                )}

                                {loan.siteVisit && (
                                    <div className="form-group">
                                        <label className="form-label">Plant Condition (1-5)</label>
                                        <StarRating value={loan.plantCondition} onChange={(n) => setLoan({ ...loan, plantCondition: n })} />
                                    </div>
                                )}

                                {loan.siteVisit && (
                                    <div className="form-group">
                                        <label className="form-label">Capacity Utilization %</label>
                                        <input className="form-input" type="number" placeholder="72" min="0" max="100"
                                            value={loan.capacityUtilization} onChange={(e) => setLoan({ ...loan, capacityUtilization: e.target.value })} />
                                    </div>
                                )}

                                {loan.siteVisit && (
                                    <div className="form-group">
                                        <label className="form-label">Management Transparency (1-5)</label>
                                        <StarRating value={loan.mgmtTransparency} onChange={(n) => setLoan({ ...loan, mgmtTransparency: n })} />
                                    </div>
                                )}
                            </div>
                        </div>

                        {error && (
                            <div style={{ background: 'var(--red-bg)', border: '1px solid var(--red)', color: 'var(--red-text)', padding: '12px 16px', borderRadius: 8, fontSize: 13, marginBottom: 16 }}>
                                ⚠️ {error}
                            </div>
                        )}

                        <div className={styles.tabActions}>
                            <button className="btn-secondary" onClick={() => setTab(1)}>← Back</button>
                            <button className="btn-primary" id="btn-create-case" onClick={handleSubmit} disabled={submitting}>
                                {submitting ? <><span className="spinner" /> Creating…</> : 'Create Case & Continue →'}
                            </button>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}
