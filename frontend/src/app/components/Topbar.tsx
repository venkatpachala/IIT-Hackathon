'use client';

import Link from 'next/link';
import styles from './Topbar.module.css';

interface TopbarProps {
    userName?: string;
    role?: 'manager' | 'approver';
    links?: { label: string; href: string }[];
}

export default function Topbar({ userName = 'User', role = 'manager', links = [] }: TopbarProps) {
    return (
        <header className={styles.topbar}>
            <div className={styles.left}>
                <Link href={role === 'manager' ? '/dashboard/manager' : '/dashboard/approver'} className={styles.brand}>
                    <span>🏦</span>
                    <span className={styles.brandName}>Intelli-Credit</span>
                </Link>
                <nav className={styles.links}>
                    {links.map((link) => (
                        <Link key={link.href} href={link.href} className={styles.link}>
                            {link.label}
                        </Link>
                    ))}
                </nav>
            </div>
            <div className={styles.right}>
                <span className={styles.roleTag}>{role === 'manager' ? 'Credit Manager' : 'Sr. Approver'}</span>
                <div className={styles.userBadge}>
                    <div className={styles.avatar}>{userName.charAt(0).toUpperCase()}</div>
                    <span>{userName}</span>
                    <span className={styles.chevron}>▾</span>
                </div>
            </div>
        </header>
    );
}
