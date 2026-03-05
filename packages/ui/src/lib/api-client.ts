// This project was developed with assistance from AI tools.

export class ApiError extends Error {
    status: number;
    detail: string;
    type: string;
    request_id?: string;

    constructor(status: number, body: { type?: string; title?: string; detail?: string; request_id?: string }) {
        super(body.detail || body.title || `HTTP ${status}`);
        this.name = 'ApiError';
        this.status = status;
        this.detail = body.detail || '';
        this.type = body.type || 'about:blank';
        this.request_id = body.request_id;
    }
}

let _getHeaders: () => Record<string, string> = () => ({});

export function setAuthHeaderProvider(fn: () => Record<string, string>): void {
    _getHeaders = fn;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers);
    const authHeaders = _getHeaders();
    for (const [k, v] of Object.entries(authHeaders)) {
        headers.set(k, v);
    }
    if (!headers.has('Content-Type') && init?.body && !(init.body instanceof FormData)) {
        headers.set('Content-Type', 'application/json');
    }

    const response = await fetch(path, { ...init, headers });

    if (!response.ok) {
        let body: Record<string, unknown> = {};
        try {
            body = await response.json();
        } catch {
            // non-JSON error
        }
        throw new ApiError(response.status, body as { type?: string; title?: string; detail?: string; request_id?: string });
    }

    if (response.status === 204) return undefined as T;

    return response.json() as Promise<T>;
}

export function apiGet<T>(path: string): Promise<T> {
    return apiFetch<T>(path);
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
    return apiFetch<T>(path, {
        method: 'POST',
        body: body instanceof FormData ? body : JSON.stringify(body),
    });
}

export function apiPatch<T>(path: string, body: unknown): Promise<T> {
    return apiFetch<T>(path, {
        method: 'PATCH',
        body: JSON.stringify(body),
    });
}

export function apiDelete<T>(path: string): Promise<T> {
    return apiFetch<T>(path, { method: 'DELETE' });
}
