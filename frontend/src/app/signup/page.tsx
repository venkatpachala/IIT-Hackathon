'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { apiRegister } from '@/lib/api';
import styles from './SignupPage.module.css';

const ROLES = [
    {
        value: 'credit_manager',
        title: 'Credit Manager',
        desc: 'Create cases, upload documents, run AI analysis, generate CAM reports',
        icon: '📊',
    },
    {
        value: 'senior_approver',
        title: 'Senior Approver',
        desc: 'Review CAM reports, make final credit decisions, manage approval queue',
        icon: '✅',
    },
];

export default function SignupPage() {
    const router = useRouter();
    const [step, setStep] = useState<1 | 2>(1);
    const [selectedRole, setSelectedRole] = useState('');
    const [form, setForm] = useState({
        fullName: '', email: '', branch: '', password: '', confirmPassword: '',
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
        setForm((p) => ({ ...p, [e.target.name]: e.target.value }));

    const handleRoleSelect = (role: string) => {
        setSelectedRole(role);
        setStep(2);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (form.password !== form.confirmPassword) {
            setError('Passwords do not match.');
            return;
        }
        if (form.password.length < 6) {
            setError('Password must be at least 6 characters.');
            return;
        }
        setLoading(true);
        try {
            const data = await apiRegister({
                name: form.fullName,
                email: form.email,
                password: form.password,
                role: selectedRole,
                branch: form.branch || undefined,
            });
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_name', data.name);
            localStorage.setItem('user_role', data.role);
            localStorage.setItem('user_id', data.user_id);
            setSuccess(true);
            setTimeout(() => {
                if (data.role === 'senior_approver') {
                    router.push('/dashboard/approver');
                } else {
                    router.push('/dashboard/manager');
                }
            }, 1800);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Registration failed');
        } finally {
            setLoading(false);
        }
    };

    if (success) {
        return (
            <div className={styles.root}>
                <div className={styles.bgOrbs}><div className={styles.orb1} /><div className={styles.orb2} /></div>
                <div className={styles.successScreen}>
                    <div className={styles.successIcon}>🎉</div>
                    <h2 className={styles.successTitle}>Account Created!</h2>
                    <p className={styles.successDesc}>
                        Welcome to Intelli-Credit. Taking you to your dashboard…
                    </p>
                    <span className="spinner spinner-lg" style={{ margin: '0 auto' }} />
                </div>
            </div>
        );
    }

    return (
        <div className={styles.root}>
            <div className={styles.bgOrbs}>
                <div className={styles.orb1} />
                <div className={styles.orb2} />
            </div>
            <div className={styles.bgGrid} />

            <div className={styles.container}>
                {/* Header */}
                <div className={styles.header}>
                    <div className={styles.logoRow}>
                        <div className={styles.logoMark}><span>IC</span></div>
                        <span className={styles.logoText}>Intelli-Credit</span>
                    </div>
                    <div className={styles.stepIndicator}>
                        <div className={`${styles.stepDot} ${step >= 1 ? styles.stepDotActive : ''}`}>1</div>
                        <div className={`${styles.stepLine} ${step >= 2 ? styles.stepLineActive : ''}`} />
                        <div className={`${styles.stepDot} ${step >= 2 ? styles.stepDotActive : ''}`}>2</div>
                    </div>
                </div>

                {/* Step 1: Role Selection */}
                {step === 1 && (
                    <div className={`${styles.card} animate-scale-in`}>
                        <h1 className={styles.cardTitle}>Choose your role</h1>
                        <p className={styles.cardSubtitle}>
                            Select the role that best describes your position. This determines your access level.
                        </p>

                        <div className={styles.roleGrid}>
                            {ROLES.map((r) => (
                                <button
                                    key={r.value}
                                    type="button"
                                    id={`role-${r.value}`}
                                    className={`${styles.roleCard} ${selectedRole === r.value ? styles.roleCardActive : ''}`}
                                    onClick={() => handleRoleSelect(r.value)}
                                >
                                    <div className={styles.roleIcon}>{r.icon}</div>
                                    <div className={styles.roleTitle}>{r.title}</div>
                                    <div className={styles.roleDesc}>{r.desc}</div>
                                    <div className={styles.roleArrow}>Select →</div>
                                </button>
                            ))}
                        </div>

                        <div className={styles.cardFooter}>
                            <span>Already have an account?</span>
                            <Link href="/login">Sign in</Link>
                        </div>
                    </div>
                )}

                {/* Step 2: Account Details */}
                {step === 2 && (
                    <div className={`${styles.card} animate-scale-in`}>
                        <button type="button" className={styles.backBtn} onClick={() => setStep(1)}>
                            ← Change Role
                        </button>

                        <div className={styles.rolePill}>
                            {ROLES.find(r => r.value === selectedRole)?.icon}{' '}
                            {ROLES.find(r => r.value === selectedRole)?.title}
                        </div>

                        <h1 className={styles.cardTitle}>Create your account</h1>
                        <p className={styles.cardSubtitle}>Fill in your details to get started</p>

                        <form className={styles.form} onSubmit={handleSubmit}>
                            <div className={styles.twoCol}>
                                <div className="form-group">
                                    <label className="form-label" htmlFor="fullName">Full Name *</label>
                                    <input
                                        id="fullName" name="fullName" type="text"
                                        className="form-input" placeholder="Priya Sharma"
                                        value={form.fullName} onChange={handleChange} required
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label" htmlFor="email">Work Email *</label>
                                    <input
                                        id="email" name="email" type="email"
                                        className="form-input" placeholder="priya@hdfc.com"
                                        value={form.email} onChange={handleChange} required
                                    />
                                </div>
                            </div>

                            <div className="form-group">
                                <label className="form-label" htmlFor="branch">Branch / Department</label>
                                <input
                                    id="branch" name="branch" type="text"
                                    className="form-input" placeholder="Mumbai — Corporate Credit"
                                    value={form.branch} onChange={handleChange}
                                />
                            </div>

                            <div className={styles.twoCol}>
                                <div className="form-group">
                                    <label className="form-label" htmlFor="password">Password *</label>
                                    <input
                                        id="password" name="password" type="password"
                                        className="form-input" placeholder="Min 6 characters"
                                        value={form.password} onChange={handleChange} required
                                    />
                                </div>
                                <div className="form-group">
                                    <label className="form-label" htmlFor="confirmPassword">Confirm Password *</label>
                                    <input
                                        id="confirmPassword" name="confirmPassword" type="password"
                                        className="form-input" placeholder="••••••••"
                                        value={form.confirmPassword} onChange={handleChange} required
                                    />
                                </div>
                            </div>

                            {error && <div className="form-error"><span>⚠️</span> {error}</div>}

                            <button
                                type="submit" id="btn-create-account"
                                className={`btn-primary ${styles.submitBtn}`}
                                disabled={loading}
                            >
                                {loading ? <><span className="spinner" /> Creating account…</> : 'Create Account →'}
                            </button>
                        </form>

                        <div className={styles.cardFooter}>
                            <span>Already have an account?</span>
                            <Link href="/login">Sign in</Link>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
