'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Sidebar from '../../../components/Sidebar';
import { apiGetStatus, PipelineStatus } from '@/lib/api';
import styles from './ProgressPage.module.css';

function ElapsedTimer({ start }: { start: Date }) {
    const [elapsed, setElapsed] = useState(0);
    useEffect(() => {
        const t = setInterval(() => setElapsed(Math.floor((Date.now() - start.getTime()) / 1000)), 1000);
        return () => clearInterval(t);
    }, [start]);
    const m = Math.floor(elapsed / 60), s = elapsed % 60;
    return <span>{m > 0 ? `${m}m ` : ''}{s}s</span>;
}

const STATUS_ICONS: Record<string, string> = {
    complete: '✅', running: '⚙️', waiting: '⏳', error: '❌',
};

export default function ProgressPage() {
    const { caseId } = useParams<{ caseId: string }>();
    const router = useRouter();
    const [status, setStatus] = useState<PipelineStatus | null>(null);
    const [error, setError] = useState('');
    const [startTime] = useState(new Date());
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchStatus = async () => {
        try {
            const data = await apiGetStatus(caseId);
            setStatus(data);
            if (data.is_complete) {
                if (pollRef.current) clearInterval(pollRef.current);
                setTimeout(() => router.push(`/cases/${caseId}/cam`), 1500);
            }
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Status check failed');
        }
    };

    useEffect(() => {
        fetchStatus();
        pollRef.current = setInterval(fetchStatus, 4000);
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [caseId]);

    const stages = status?.stages ?? [];
    const done = stages.filter(s => s.status === 'complete').length;
    const total = stages.length || 6;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    const running = stages.find(s => s.status === 'running');

    return (
        <div className={styles.layout}>
            <Sidebar role="manager" />

            <main className={styles.main}>
                <div className={styles.pageHeader}>
                    <div>
                        <div className={`mono ${styles.caseId}`}>{caseId}</div>
                        <h1 className={styles.pageTitle}>Analysis in Progress…</h1>
                        {running && (
                            <div className={styles.currentStage}>
                                <span className="animate-pulse">⚙️</span> {running.label}
                            </div>
                        )}
                    </div>
                    <div className={styles.elapsedBadge}>⏱ <ElapsedTimer start={startTime} /></div>
                </div>

                {/* Overall progress bar */}
                <div className={styles.overallBar}>
                    <div className={styles.overallInfo}>
                        <span>Pipeline Progress</span>
                        <span className={styles.overallPct}>{pct}%</span>
                    </div>
                    <div className={styles.overallTrack}>
                        <div className={styles.overallFill} style={{ width: `${pct}%` }} />
                    </div>
                </div>

                {error && (
                    <div className="form-error" style={{ marginBottom: 16 }}>⚠️ {error}</div>
                )}

                {/* Stage list */}
                <div className={styles.pipelineCard}>
                    <div className={styles.pipelineHeader}>
                        <span className={styles.phLabel}>Pipeline Stages</span>
                        <span className={styles.phCount}>{done} / {total} complete</span>
                    </div>

                    <div className={styles.stageList}>
                        {stages.length === 0
                            ? Array.from({ length: 6 }).map((_, i) => (
                                <div key={i} className={styles.stageSkeleton}>
                                    <div className="skeleton" style={{ width: 36, height: 36, borderRadius: '50%' }} />
                                    <div>
                                        <div className="skeleton" style={{ width: 180, height: 14, marginBottom: 6 }} />
                                        <div className="skeleton" style={{ width: 120, height: 11 }} />
                                    </div>
                                </div>
                            ))
                            : stages.map((stage, idx) => (
                                <div key={stage.id}
                                    className={`${styles.stageItem} ${styles[`stage_${stage.status}`]}`}
                                    style={{ animationDelay: `${idx * 0.08}s` }}>

                                    {idx < stages.length - 1 && (
                                        <div className={`${styles.connector} ${stage.status === 'complete' ? styles.connectorDone : ''}`} />
                                    )}

                                    <div className={styles.stageIcon}>
                                        {stage.status === 'running'
                                            ? <span className={`${styles.spinnerIcon} animate-pulse`}>⚙️</span>
                                            : <span>{STATUS_ICONS[stage.status]}</span>}
                                    </div>

                                    <div className={styles.stageInfo}>
                                        <div className={styles.stageLabel}>{stage.label}</div>
                                        <div className={styles.stageDetail}>{stage.detail}</div>
                                    </div>

                                    <div className={styles.stageStatus}>
                                        {stage.status === 'complete' && <span className={styles.sComp}>Complete</span>}
                                        {stage.status === 'running' && (
                                            <span className={styles.sRun}>
                                                <span className="spinner" style={{ width: 10, height: 10 }} />
                                                Running…
                                            </span>
                                        )}
                                        {stage.status === 'waiting' && <span className={styles.sWait}>Waiting</span>}
                                        {stage.status === 'error' && <span className={styles.sErr}>Error</span>}
                                    </div>
                                </div>
                            ))}
                    </div>
                </div>

                {/* Live logs */}
                {status?.logs && status.logs.length > 0 && (
                    <div className={styles.logsCard}>
                        <div className={styles.logsHeader}>📋 Live Logs</div>
                        <div className={styles.logsList}>
                            {status.logs.map((log, i) => (
                                <div key={i} className={styles.logLine}>
                                    <span className={`mono ${styles.logTs}`}>
                                        {new Date(log.ts).toLocaleTimeString('en-IN')}
                                    </span>
                                    <span className={`${styles.logStage} ${styles[`log_${log.status}`]}`}>
                                        {log.stage}
                                    </span>
                                    <span className={styles.logMsg}>{log.message}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Footer info */}
                <div className={styles.footerCards}>
                    <div className={styles.infoCard}>
                        <div className={styles.infoIcon}>⏳</div>
                        <div>
                            <div className={styles.infoTitle}>Estimated time remaining</div>
                            <div className={styles.infoVal}>~{Math.max(1, Math.ceil((total - done) * 1.5))} minutes</div>
                        </div>
                    </div>
                    <div className={styles.infoCard}>
                        <div className={styles.infoIcon}>📬</div>
                        <div>
                            <div className={styles.infoTitle}>You can safely leave this page</div>
                            <div className={styles.infoVal}>CAM will be ready when complete</div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
