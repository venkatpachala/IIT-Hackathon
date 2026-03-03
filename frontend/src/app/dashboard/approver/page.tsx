'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import Sidebar from '../../components/Sidebar';
import { apiListCases, CaseListItem } from '@/lib/api';
import styles from './ApproverDashboard.module.css';

const riskLabel: Record<string, string> = {
    GREEN: '🟢 GREEN', AMBER: '🟡 AMBER', RED: '🔴 RED', BLACK: '⚫ BLACK',
};
const riskClass: Record<string, string> = {
    GREEN: 'badge-green', AMBER: 'badge-amber', RED: 'badge-red', BLACK: 'badge-black',
};

function formatCr(n?: number): string {
    if (!n || n === 0) return '—';
    return `₹${(n / 10000000).toFixed(1)} Cr`;
}

export default function ApproverDashboardPage() {
    const router = useRouter();
    const [userName, setUserName] = useState('');
    const [queue, setQueue] = useState<CaseListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const loadQueue = useCallback(async () => {
        try {
            setLoading(true);
            const data = await apiListCases();
            // Approvers see pending + recently decided cases
            setQueue(data);
        } catch (e: unknown) {
            if (e instanceof Error && e.message.includes('401')) {
                router.push('/login');
            } else {
                setError('Failed to load review queue');
            }
        } finally {
            setLoading(false);
        }
    }, [router]);

    useEffect(() => {
        const name = localStorage.getItem('user_name') || '';
        setUserName(name ? name.charAt(0).toUpperCase() + name.slice(1) : '');
        loadQueue();
    }, [loadQueue]);

    const pending = queue.filter(c => c.status === 'pending_approval');
    const reviewed = queue.filter(c => ['approved', 'rejected'].includes(c.status));

    return (
        <div className={styles.layout}>
            <Sidebar role="approver" activePage="/dashboard/approver" userName={userName} />

            <main className={styles.main}>
                <div className={styles.pageHeader}>
                    <div>
                        <h1 className={styles.pageTitle}>Review Queue</h1>
                        <p className={styles.pageSubtitle}>Cases awaiting your approval decision</p>
                    </div>
                    <div className={styles.pendingBadge}>{pending.length} Pending</div>
                </div>

                {/* Stats */}
                <div className={styles.statsRow}>
                    {[
                        { label: 'Awaiting Review', value: pending.length, col: 'amber', icon: '⏳' },
                        { label: 'GREEN Ratings', value: pending.filter(c => c.risk_color === 'GREEN').length, col: 'green', icon: '🟢' },
                        { label: 'RED / BLACK', value: pending.filter(c => ['RED', 'BLACK'].includes(c.risk_color)).length, col: 'red', icon: '🔴' },
                        { label: 'Decisions Made', value: reviewed.length, col: 'blue', icon: '✅' },
                    ].map((s) => (
                        <div key={s.label} className={`${styles.statCard} ${styles[`sc_${s.col}`]}`}>
                            <div className={styles.statIcon}>{s.icon}</div>
                            <div className={styles.statVal}>{s.value}</div>
                            <div className={styles.statLabel}>{s.label}</div>
                        </div>
                    ))}
                </div>

                {error && <div className="form-error" style={{ marginBottom: 16 }}>⚠️ {error}</div>}

                {loading ? (
                    <div className={styles.loadingState}>
                        <span className="spinner spinner-lg" />
                        <span>Loading review queue…</span>
                    </div>
                ) : (
                    <>
                        {/* Pending Review */}
                        <div className={styles.queueCard}>
                            <div className={styles.queueHeader}>
                                <h2 className={styles.queueTitle}>⏳ Pending Your Review</h2>
                                <span className={styles.queueCount}>{pending.length} cases</span>
                            </div>

                            {pending.length === 0 ? (
                                <div className={styles.emptyState}>
                                    <div className={styles.emptyIcon}>🎉</div>
                                    <div className={styles.emptyTitle}>All caught up!</div>
                                    <div className={styles.emptyDesc}>No cases pending your review.</div>
                                </div>
                            ) : (
                                <div className={styles.queueList}>
                                    {pending.map((item, idx) => (
                                        <div key={item.id} className={styles.queueItem}
                                            style={{ animationDelay: `${idx * 0.05}s` }}>
                                            <div className={styles.queueIndex}>
                                                {String(idx + 1).padStart(2, '0')}
                                            </div>
                                            <div className={styles.queueInfo}>
                                                <div className={styles.queueCompany}>{item.company_name}</div>
                                                <div className={`mono ${styles.queueId}`}>{item.id}</div>
                                                <div className={styles.queueMeta}>
                                                    {item.industry && <span>{item.industry}</span>}
                                                    {item.loan_amount && <span>{formatCr(item.loan_amount)} requested</span>}
                                                </div>
                                            </div>
                                            <div className={styles.queueRight}>
                                                <span className={riskClass[item.risk_color]}>
                                                    {riskLabel[item.risk_color]}
                                                </span>
                                                {item.recommended_limit !== undefined && (
                                                    <span className={styles.queueAmount}>
                                                        Rec: {formatCr(item.recommended_limit)}
                                                    </span>
                                                )}
                                                <Link
                                                    href={`/cases/${item.id}/cam`}
                                                    className={styles.viewCamBtn}
                                                >
                                                    View CAM
                                                </Link>
                                                <Link
                                                    href={`/cases/${item.id}/review`}
                                                    className="btn-primary"
                                                    id={`btn-review-${item.id}`}
                                                >
                                                    Review →
                                                </Link>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Recently Decided */}
                        {reviewed.length > 0 && (
                            <div className={styles.queueCard} style={{ marginTop: 20 }}>
                                <div className={styles.queueHeader}>
                                    <h2 className={styles.queueTitle}>✅ Recent Decisions</h2>
                                    <span className={styles.queueCount}>{reviewed.length} cases</span>
                                </div>
                                <div className={styles.queueList}>
                                    {reviewed.map((item, idx) => (
                                        <div key={item.id} className={`${styles.queueItem} ${styles.queueItemDone}`}>
                                            <div className={styles.queueIndex}>{String(idx + 1).padStart(2, '0')}</div>
                                            <div className={styles.queueInfo}>
                                                <div className={styles.queueCompany}>{item.company_name}</div>
                                                <div className={`mono ${styles.queueId}`}>{item.id}</div>
                                            </div>
                                            <div className={styles.queueRight}>
                                                <span className={riskClass[item.risk_color]}>
                                                    {riskLabel[item.risk_color]}
                                                </span>
                                                <span className={`status-pill ${item.status}`}>
                                                    {item.status === 'approved' ? '✅ Approved' : '❌ Rejected'}
                                                </span>
                                                <Link href={`/cases/${item.id}/cam`} className="btn-ghost">
                                                    View →
                                                </Link>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                )}
            </main>
        </div>
    );
}
