'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import styles from './Sidebar.module.css';

interface SidebarItem {
    icon: string;
    label: string;
    href: string;
    active?: boolean;
}

interface SidebarProps {
    role: 'manager' | 'approver';
    activePage?: string;
    userName?: string;
}

const managerItems: SidebarItem[] = [
    { icon: '📊', label: 'Dashboard', href: '/dashboard/manager' },
    { icon: '📁', label: 'My Cases', href: '/cases' },
    { icon: '➕', label: 'New Case', href: '/cases/new' },
    { icon: '⚙️', label: 'Settings', href: '/settings' },
];

const approverItems: SidebarItem[] = [
    { icon: '📋', label: 'Review Queue', href: '/dashboard/approver' },
    { icon: '✅', label: 'Completed', href: '/cases/completed' },
    { icon: '⚙️', label: 'Settings', href: '/settings' },
];

export default function Sidebar({ role, activePage, userName = 'User' }: SidebarProps) {
    const router = useRouter();
    const items = role === 'manager' ? managerItems : approverItems;

    const handleLogout = () => {
        localStorage.removeItem('access_token');
        router.push('/login');
    };

    return (
        <aside className={styles.sidebar}>
            {/* Logo */}
            <div className={styles.logo}>
                <span className={styles.logoIcon}>🏦</span>
                <span className={styles.logoText}>Intelli-Credit</span>
            </div>

            {/* Nav */}
            <nav className={styles.nav}>
                {items.map((item) => (
                    <Link
                        key={item.href}
                        href={item.href}
                        className={`${styles.navItem} ${activePage === item.href ? styles.active : ''}`}
                    >
                        <span className={styles.navIcon}>{item.icon}</span>
                        <span className={styles.navLabel}>{item.label}</span>
                    </Link>
                ))}
            </nav>

            {/* User */}
            <div className={styles.userSection}>
                <div className={styles.userInfo}>
                    <div className={styles.avatar}>{userName.charAt(0).toUpperCase()}</div>
                    <div className={styles.userDetails}>
                        <span className={styles.userName}>{userName}</span>
                        <span className={styles.userRole}>{role === 'manager' ? 'Credit Manager' : 'Sr. Approver'}</span>
                    </div>
                </div>
                <button className={styles.logoutBtn} onClick={handleLogout} title="Sign out">
                    ↗
                </button>
            </div>
        </aside>
    );
}
