// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import {
    AuditSearchResponseSchema,
    type AuditSearchResponse,
} from '@/schemas/audit';

export async function fetchAuditEvents(limit: number): Promise<AuditSearchResponse> {
    const data = await apiGet<unknown>(`/api/audit/search?limit=${limit}`);
    return AuditSearchResponseSchema.parse(data);
}

export async function fetchAuditEventsFiltered(params: {
    days?: number;
    eventType?: string;
    limit?: number;
}): Promise<AuditSearchResponse> {
    const searchParams = new URLSearchParams();
    if (params.days) searchParams.set('days', String(params.days));
    if (params.eventType) searchParams.set('event_type', params.eventType);
    if (params.limit) searchParams.set('limit', String(params.limit));
    const qs = searchParams.toString();
    const data = await apiGet<unknown>(`/api/audit/search${qs ? `?${qs}` : ''}`);
    return AuditSearchResponseSchema.parse(data);
}
