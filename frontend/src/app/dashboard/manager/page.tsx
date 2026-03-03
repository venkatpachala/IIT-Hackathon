'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import Sidebar from '../../components/Sidebar';
import { apiListCases, CaseListItem } from '@/lib/api';
import styles from './ManagerDashboard.module.css';

const riskBadge: Record<string, string> = {
    GREEN: 'badge-green', AMBER: 'badge-amber', RED: 'badge-red', BLACK: 'badge-black',
};
const riskEmoji: Record<string, string> = {
    GREEN: '🟢', AMBER: '🟡', RED: '🔴', BLACK: '⚫',
};

function statusLabel(s: string): string {
    const m: Record<string, string> = {
        draft: 'Draft', uploaded: 'Uploaded', processing: 'Processing',
        cam_ready: 'CAM Ready', pending_approval: 'Pending Approval',
        approved: 'Approved', rejected: 'Rejected', error: 'Error',
    };
    return m[s] ?? s;
}

function formatCr(n?: number): string {
    if (!n || n === 0) return '—';
    return `₹${(n / 10000000).toFixed(2)} Cr`;
}

export default function ManagerDashboardPage() {
    const router = useRouter();
    const [userName, setUserName] = useState('');
    const [cases, setCases] = useState<CaseListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const hour = new Date().getHours();
    const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

    const loadCases = useCallback(async () => {
        try {
            setLoading(true);
            const data = await apiListCases();
            setCases(data);
        } catch (e: unknown) {
            if (e instanceof Error && e.message.includes('401')) {
                router.push('/login');
            } else {
                setError('Failed to load cases');
            }
        } finally {
            setLoading(false);
        }
    }, [router]);

    useEffect(() => {
        const name = localStorage.getItem('user_name') || '';
        setUserName(name ? name.charAt(0).toUpperCase() + name.slice(1) : '');
        loadCases();
    }, [loadCases]);

    const stats = [
        { label: 'Total Cases', value: cases.length, icon: '📁', col: 'blue' },
        { label: 'In Progress', value: cases.filter(c => c.status === 'processing').length, icon: '⚙️', col: 'amber' },
        { label: 'CAM Ready', value: cases.filter(c => c.status === 'cam_ready').length, icon: '✅', col: 'green' },
        { label: 'Pending Approval', value: cases.filter(c => c.status === 'pending_approval').length, icon: '⏳', col: 'purple' },
    ];

    return (
        <div className={styles.layout}>
            <Sidebar role="manager" activePage="/dashboard/manager" userName={userName} />

            <main className={styles.main}>
                {/* Header */}
                <div className={styles.pageHeader}>
                    <div>
                        <div className={styles.greeting}>{greeting}{userName ? `, ${userName}` : ''} 👋</div>
                        <div className={styles.subline}>Your AI credit appraisal workspace</div>
                    </div>
                    <Link href="/cases/new" className="btn-primary" id="btn-new-case">
                        ➕ New Case
                    </Link>
                </div>

                {/* Stats */}
                <div className={styles.statsRow}>
                    {stats.map((s) => (
                        <div key={s.label} className={`${styles.statCard} ${styles[`sc_${s.col}`]}`}>
                            <div className={styles.statIcon}>{s.icon}</div>
                            <div className={styles.statValue}>{s.value}</div>
                            <div className={styles.statLabel}>{s.label}</div>
                        </div>
                    ))}
                </div>

                {/* Cases table */}
                <div className={styles.casesSection}>
                    <div className={styles.sectionHeader}>
                        <h2 className={styles.sectionTitle}>Recent Cases</h2>
                        <button onClick={loadCases} className="btn-ghost">↻ Refresh</button>
                    </div>

                    {error && <div className="form-error" style={{ marginBottom: 16 }}>⚠️ {error}</div>}

                    {loading ? (
                        <div className={styles.loadingState}>
                            <span className="spinner spinner-lg" />
                            <span>Loading your cases…</span>
                        </div>
                    ) : cases.length === 0 ? (
                        <div className={styles.emptyState}>
                            <div className={styles.emptyIcon}>📭</div>
                            <div className={styles.emptyTitle}>No cases yet</div>
                            <div className={styles.emptyDesc}>Create your first credit appraisal case to get started.</div>
                            <Link href="/cases/new" className="btn-primary" style={{ marginTop: 16 }}>
                                ➕ Create First Case
                            </Link>
                        </div>
                    ) : (
                        <div className={styles.tableWrapper}>
                            <table className={styles.table}>
                                <thead>
                                    <tr>
                                        <th>Case ID</th>
                                        <th>Company</th>
                                        <th>Industry</th>
                                        <th>Risk</th>
                                        <th>Amount</th>
                                        <th>Status</th>
                                        <th>Updated</th>
                                        <th>Action</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {cases.map((c) => (
                                        <tr key={c.id} className={styles.tableRow}>
                                            <td className={`mono ${styles.caseId}`}>{c.id}</td>
                                            <td className={styles.companyName}>{c.company_name}</td>
                                            <td className={styles.industry}>{c.industry || '—'}</td>
                                            <td>
                                                <span className={riskBadge[c.risk_color]}>
                                                    {riskEmoji[c.risk_color]} {c.risk_color}
                                                </span>
                                            </td>
                                            <td className={styles.amount}>{formatCr(c.loan_amount)}</td>
                                            <td>
                                                <span className={`status-pill ${c.status}`}>
                                                    {statusLabel(c.status)}
                                                </span>
                                            </td>
                                            <td className={styles.date}>
                                                {c.updated_at ? new Date(c.updated_at).toLocaleDateString('en-IN') : '—'}
                                            </td>
                                            <td>
                                                {c.status === 'cam_ready' || c.status === 'approved' || c.status === 'rejected' || c.status === 'pending_approval' ? (
                                                    <Link href={`/cases/${c.id}/cam`} className={styles.openBtn}>
                                                        View CAM →
                                                    </Link>
                                                ) : c.status === 'processing' ? (
                                                    <Link href={`/cases/${c.id}/progress`} className={styles.openBtn}>
                                                        Track →
                                                    </Link>
                                                ) : (
                                                    <Link href={`/cases/${c.id}/upload`} className={styles.openBtn}>
                                                        Continue →
                                                    </Link>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* Quick actions */}
                <div className={styles.quickActions}>
                    <Link href="/cases/new" className={styles.qa} id="q-new-case">
                        <span className={styles.qaIcon}>➕</span>
                        <span className={styles.qaLabel}>New Case</span>
                        <span className={styles.qaDesc}>Start a fresh credit appraisal</span>
                    </Link>
                    <button onClick={loadCases} className={styles.qa}>
                        <span className={styles.qaIcon}>↻</span>
                        <span className={styles.qaLabel}>Refresh</span>
                        <span className={styles.qaDesc}>Reload your case list</span>
                    </button>
                </div>
            </main>
        </div>
    );
}
