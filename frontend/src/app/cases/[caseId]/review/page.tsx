'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import Sidebar from '../../../components/Sidebar';
import { apiSubmitReview, apiGetCAM, CAMData } from '@/lib/api';
import styles from './ReviewPage.module.css';

const DECISIONS = [
    { value: 'approve', label: '✅ Approve as Recommended', color: 'green' },
    { value: 'approve_modified', label: '🟡 Approve with Modifications', color: 'amber' },
    { value: 'send_back', label: '↩️ Send Back for More Info', color: 'blue' },
    { value: 'reject', label: '❌ Reject Application', color: 'red' },
];

export default function ReviewPage() {
    const { caseId } = useParams<{ caseId: string }>();
    const router = useRouter();

    const [cam, setCam] = useState<CAMData | null>(null);
    const [decision, setDecision] = useState('');
    const [modLimit, setModLimit] = useState('');
    const [modRate, setModRate] = useState('');
    const [conditions, setConditions] = useState('');
    const [comments, setComments] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [submitted, setSubmitted] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        apiGetCAM(caseId).then(setCam).catch(() => { });
    }, [caseId]);

    const handleSubmit = async () => {
        if (!decision || !comments.trim()) {
            setError('Please select a decision and add your comments.');
            return;
        }
        setError('');
        setSubmitting(true);
        try {
            await apiSubmitReview(caseId, {
                decision,
                modified_limit: modLimit ? parseFloat(modLimit) : undefined,
                modified_rate: modRate ? parseFloat(modRate) : undefined,
                conditions: conditions || undefined,
                comments,
            });
            setSubmitted(true);
            setTimeout(() => router.push('/dashboard/approver'), 2500);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Submission failed');
        } finally {
            setSubmitting(false);
        }
    };

    if (submitted) {
        return (
            <div className={styles.layout}>
                <Sidebar role="approver" />
                <main className={styles.main}>
                    <div className={styles.successScreen}>
                        <div className={styles.successIcon}>
                            {decision === 'reject' ? '❌' : decision === 'approve' ? '✅' : '🟡'}
                        </div>
                        <h2 className={styles.successTitle}>
                            {decision === 'approve' ? 'Case Approved!'
                                : decision === 'approve_modified' ? 'Approved with Modifications'
                                    : decision === 'reject' ? 'Case Rejected'
                                        : 'Case Sent Back for Review'}
                        </h2>
                        <p className={styles.successDesc}>Redirecting to your dashboard…</p>
                        <span className="spinner spinner-lg" style={{ margin: '0 auto' }} />
                    </div>
                </main>
            </div>
        );
    }

    return (
        <div className={styles.layout}>
            <Sidebar role="approver" activePage="/dashboard/approver" />

            <main className={styles.main}>
                <div className={styles.pageHeader}>
                    <div>
                        <Link href="/dashboard/approver" className={styles.backLink}>← Review Queue</Link>
                        <h1 className={styles.pageTitle}>Approver Review</h1>
                        <div className={`mono ${styles.caseId}`}>{caseId}</div>
                    </div>
                    <div className={styles.reviewerBadge}>👤 Senior Approver</div>
                </div>

                {/* CAM Summary */}
                {cam && (
                    <div className={styles.camEmbed}>
                        <div className={styles.camEmbedHeader}>
                            <span>📋 Credit Appraisal Summary</span>
                            <Link href={`/cases/${caseId}/cam`} className={styles.viewFullBtn}>
                                View Full CAM ↗
                            </Link>
                        </div>
                        <div className={styles.camSummaryGrid}>
                            {[
                                { label: 'Company', value: cam.company_name },
                                { label: 'AI Decision', value: `${cam.decision_color === 'GREEN' ? '🟢' : cam.decision_color === 'AMBER' ? '🟡' : cam.decision_color === 'RED' ? '🔴' : '⚫'} ${cam.decision}` },
                                { label: 'Recommended Limit', value: `₹${(cam.recommended_limit / 10000000).toFixed(2)} Cr` },
                                { label: 'Requested Limit', value: `₹${(cam.requested_limit / 10000000).toFixed(2)} Cr` },
                                { label: 'Interest Rate', value: `${cam.interest_rate.toFixed(2)}% p.a.` },
                                { label: 'Composite Score', value: `${cam.composite_score} / 100` },
                            ].map(item => (
                                <div key={item.label} className={styles.camSummaryItem}>
                                    <div className={styles.camSummaryLabel}>{item.label}</div>
                                    <div className={styles.camSummaryValue}>{item.value}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Decision panel */}
                <div className={styles.section}>
                    <div className={styles.sectionTitle}>Your Decision *</div>
                    <div className={styles.decisionGrid}>
                        {DECISIONS.map(d => (
                            <button
                                key={d.value}
                                className={`${styles.decisionBtn} ${styles[`db_${d.color}`]} ${decision === d.value ? styles.decisionBtnActive : ''}`}
                                onClick={() => setDecision(d.value)}
                                id={`decision-${d.value}`}
                                type="button"
                            >
                                {d.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Modifications */}
                {decision === 'approve_modified' && (
                    <div className={`${styles.section} animate-fade-in`}>
                        <div className={styles.sectionTitle}>Modified Terms</div>
                        <div className={styles.modGrid}>
                            <div className="form-group">
                                <label className="form-label">Modified Limit (₹)</label>
                                <input className="form-input" placeholder="e.g. 80000000"
                                    value={modLimit} onChange={e => setModLimit(e.target.value)} />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Modified Interest Rate (%)</label>
                                <input className="form-input" placeholder="e.g. 11.00"
                                    value={modRate} onChange={e => setModRate(e.target.value)} />
                            </div>
                            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                                <label className="form-label">Sanction Conditions</label>
                                <textarea className="form-input" rows={3}
                                    placeholder="1. Weekly stock statements required&#10;2. Collateral valuation within 30 days"
                                    value={conditions} onChange={e => setConditions(e.target.value)} />
                            </div>
                        </div>
                    </div>
                )}

                {/* Comments */}
                <div className={styles.section}>
                    <div className={styles.sectionTitle}>Approver Comments *</div>
                    <textarea
                        className={`form-input ${styles.commentsArea}`}
                        rows={5}
                        placeholder="Enter your review comments, observations, and rationale for the decision…"
                        value={comments}
                        onChange={e => setComments(e.target.value)}
                        id="approver-comments"
                    />
                    <div className={styles.commentsHint}>
                        These comments will be recorded in the audit trail.
                    </div>
                </div>

                {error && <div className="form-error" style={{ marginBottom: 16 }}>⚠️ {error}</div>}

                <div className={styles.submitRow}>
                    <Link href="/dashboard/approver" className="btn-secondary">Cancel</Link>
                    <button
                        id="btn-submit-review"
                        className={`btn-primary ${decision === 'reject' ? 'btn-danger' : ''}`}
                        onClick={handleSubmit}
                        disabled={!decision || !comments.trim() || submitting}
                    >
                        {submitting
                            ? <><span className="spinner" /> Submitting…</>
                            : `Submit Decision →`}
                    </button>
                </div>
            </main>
        </div>
    );
}
