'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiLogin } from '@/lib/api';
import styles from './LoginPage.module.css';

export default function LoginPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const sessionExpired = searchParams.get('reason') === 'session_expired';

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);


    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const data = await apiLogin(email, password);
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_name', data.name);
            localStorage.setItem('user_role', data.role);
            localStorage.setItem('user_id', data.user_id);
            if (data.role === 'senior_approver') {
                router.push('/dashboard/approver');
            } else {
                router.push('/dashboard/manager');
            }
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.root}>
            {/* Animated background */}
            <div className={styles.bgOrbs}>
                <div className={styles.orb1} />
                <div className={styles.orb2} />
                <div className={styles.orb3} />
            </div>
            <div className={styles.bgGrid} />

            {/* Left brand panel */}
            <div className={styles.leftPanel}>
                <div className={styles.brand}>
                    <div className={styles.logoMark}>
                        <span>IC</span>
                    </div>
                    <h1 className={styles.brandName}>Intelli‑Credit</h1>
                    <p className={styles.brandTagline}>
                        AI-Powered Credit Appraisal Platform for Indian Banking
                    </p>
                </div>

                <div className={styles.features}>
                    {[
                        { icon: '⚡', title: 'CAM in Minutes', desc: 'Not days. AI extracts financials instantly.' },
                        { icon: '🔍', title: '5-Source Research', desc: 'RBI · MCA21 · eCourts · GSTN · News' },
                        { icon: '🛡️', title: 'Five Cs Scorecard', desc: 'AI-powered risk assessment framework' },
                        { icon: '📋', title: 'Full Audit Trail', desc: 'Every decision documented & traceable' },
                    ].map((f) => (
                        <div key={f.title} className={styles.featureItem}>
                            <span className={styles.featureIcon}>{f.icon}</span>
                            <div>
                                <div className={styles.featureTitle}>{f.title}</div>
                                <div className={styles.featureDesc}>{f.desc}</div>
                            </div>
                        </div>
                    ))}
                </div>

                <div className={styles.versionTag}>v2.0 · Production Build</div>
            </div>

            {/* Right login form */}
            <div className={styles.rightPanel}>
                <div className={styles.formCard}>
                    <div className={styles.formHeader}>
                        <h2 className={styles.formTitle}>Welcome back</h2>
                        <p className={styles.formSubtitle}>Sign in to your workspace</p>
                    </div>

                    {/* Session expired banner */}
                    {sessionExpired && (
                        <div style={{
                            background: 'rgba(255,152,0,0.12)',
                            border: '1px solid rgba(255,152,0,0.4)',
                            borderRadius: '8px',
                            padding: '10px 14px',
                            marginBottom: '16px',
                            color: '#ff9800',
                            fontSize: '13px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                        }}>
                            <span>⏱️</span>
                            <span>Your session expired. Please sign in again to continue.</span>
                        </div>
                    )}

                    <form className={styles.form} onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label className="form-label" htmlFor="email">Work Email</label>
                            <input
                                id="email" type="email" className="form-input"
                                placeholder="priya@hdfc.com"
                                value={email} onChange={(e) => setEmail(e.target.value)}
                                autoComplete="email" required
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="password">Password</label>
                            <input
                                id="password" type="password" className="form-input"
                                placeholder="••••••••••"
                                value={password} onChange={(e) => setPassword(e.target.value)}
                                autoComplete="current-password" required
                            />
                        </div>

                        {error && (
                            <div className="form-error">
                                <span>⚠️</span> {error}
                            </div>
                        )}

                        <button
                            type="submit" id="btn-sign-in"
                            className={`btn-primary ${styles.submitBtn}`}
                            disabled={loading}
                        >
                            {loading ? <><span className="spinner" /> Signing in…</> : 'Sign In →'}
                        </button>
                    </form>

                    <div className={styles.formFooter}>
                        <span className={styles.footerText}>{"Don't have an account?"}</span>
                        <Link href="/signup" className={styles.footerLink}>Request access</Link>
                    </div>
                </div>
            </div>
        </div>
    );
}
