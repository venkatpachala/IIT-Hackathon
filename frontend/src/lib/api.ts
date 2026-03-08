/**
 * /src/lib/api.ts
 * Centralised API client for Intelli-Credit backend.
 * All calls go through this — no fetch() scattered in components.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export function getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('access_token');
}

function authHeaders(): HeadersInit {
    const token = getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T = unknown>(
    path: string,
    options: RequestInit = {},
): Promise<T> {
    const res = await fetch(`${BASE}${path}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...authHeaders(),
            ...(options.headers ?? {}),
        },
    });

    if (!res.ok) {
        // ── Auto-logout on 401: token expired or missing ──────────────
        if (res.status === 401 && typeof window !== 'undefined') {
            // Clear ALL auth keys so the stale role/name don't stay behind
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_name');
            localStorage.removeItem('user_role');
            localStorage.removeItem('user_id');
            // Redirect to login with a hint message
            window.location.href = '/login?reason=session_expired';
            // Return a never-resolving promise — navigation is in progress
            return new Promise(() => { });
        }
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new APIError(res.status, body.detail ?? 'Request failed');
    }

    return res.json() as Promise<T>;
}

export class APIError extends Error {
    constructor(public status: number, message: string) {
        super(message);
    }
}

// ── Auth ────────────────────────────────────────────────────

export interface AuthResponse {
    access_token: string;
    role: 'credit_manager' | 'senior_approver';
    name: string;
    user_id: string;
    branch?: string;
}

export async function apiRegister(payload: {
    name: string;
    email: string;
    password: string;
    role: string;
    branch?: string;
}): Promise<AuthResponse> {
    return request('/auth/register', { method: 'POST', body: JSON.stringify(payload) });
}

export async function apiLogin(email: string, password: string): Promise<AuthResponse> {
    return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
}

export async function apiMe(): Promise<{
    id: string; name: string; email: string; role: string; branch?: string;
}> {
    return request('/auth/me');
}

// ── Cases ────────────────────────────────────────────────────

export interface CaseListItem {
    id: string;
    company_name: string;
    status: string;
    pipeline_stage: string;
    risk_color: 'GREEN' | 'AMBER' | 'RED' | 'BLACK';
    decision?: string;
    loan_amount?: number;
    loan_type?: string;
    industry?: string;
    recommended_limit?: number;
    composite_score?: number;
    created_at?: string;
    updated_at?: string;
}

export async function apiListCases(statusFilter?: string): Promise<CaseListItem[]> {
    const qs = statusFilter ? `?status_filter=${statusFilter}` : '';
    return request(`/cases${qs}`);
}

export async function apiCreateCase(payload: {
    company: Record<string, unknown>;
    promoters: unknown[];
    loan: Record<string, unknown>;
}): Promise<{ case_id: string; status: string }> {
    return request('/cases', { method: 'POST', body: JSON.stringify(payload) });
}

export async function apiGetCase(caseId: string): Promise<CaseListItem> {
    return request(`/cases/${caseId}`);
}

// ── Upload ───────────────────────────────────────────────────

export async function apiUploadDocs(
    caseId: string,
    files: File[],
    onProgress?: (pct: number) => void,
): Promise<{ uploaded: string[]; count: number }> {
    const form = new FormData();
    files.forEach((f) => form.append('files', f));

    const res = await fetch(`${BASE}/cases/${caseId}/upload`, {
        method: 'POST',
        headers: { ...authHeaders() } as Record<string, string>,
        body: form,
    });
    if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new APIError(res.status, body.detail ?? 'Upload failed');
    }
    return res.json();
}

// ── Pipeline ─────────────────────────────────────────────────

export async function apiStartPipeline(caseId: string): Promise<{ message: string }> {
    return request(`/cases/${caseId}/start`, { method: 'POST' });
}

export interface PipelineStatus {
    case_id: string;
    status: string;
    pipeline_stage: string;
    is_complete: boolean;
    stages: {
        id: string;
        label: string;
        detail: string;
        status: 'complete' | 'running' | 'waiting' | 'error';
    }[];
    logs: { stage: string; status: string; message: string; ts: string }[];
}

export async function apiGetStatus(caseId: string): Promise<PipelineStatus> {
    return request(`/cases/${caseId}/status`);
}

// ── CAM ─────────────────────────────────────────────────────

export interface CAMData {
    case_id: string;
    company_name: string;
    generated_at: string;
    prepared_by: string;
    decision: string;
    decision_color: 'GREEN' | 'AMBER' | 'RED' | 'BLACK';
    recommended_limit: number;
    requested_limit: number;
    interest_rate: number;
    tenor: number;
    composite_score: number;
    decision_summary: string;
    five_c_scores: { name: string; score: number; max: number; color: string }[];
    risk_flags: { level: string; flags: string[] }[];
    rate_derivation: { label: string; rate: number; is_base?: boolean }[];
    research_risk_band?: string;
    research_risk_score?: number;
    extraction_flags?: number;
    research_flags?: number;
    tags?: string[];
}

export async function apiGetCAM(caseId: string): Promise<CAMData> {
    return request(`/cases/${caseId}/cam`);
}

export async function apiSendToApprover(caseId: string): Promise<{ message: string }> {
    return request(`/cases/${caseId}/send-to-approver`, { method: 'POST' });
}

// ── Review ────────────────────────────────────────────────────

export async function apiSubmitReview(
    caseId: string,
    payload: {
        decision: string;
        modified_limit?: number;
        modified_rate?: number;
        conditions?: string;
        comments: string;
    },
): Promise<{ message: string; new_status: string }> {
    return request(`/cases/${caseId}/review`, { method: 'POST', body: JSON.stringify(payload) });
}
