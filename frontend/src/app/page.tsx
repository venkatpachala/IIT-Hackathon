'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      // Try to decode role from token
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (payload.role === 'senior_approver') {
          router.replace('/dashboard/approver');
        } else {
          router.replace('/dashboard/manager');
        }
      } catch {
        router.replace('/login');
      }
    } else {
      router.replace('/login');
    }
  }, [router]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      <div className="spinner" style={{ width: 32, height: 32 }} />
    </div>
  );
}
