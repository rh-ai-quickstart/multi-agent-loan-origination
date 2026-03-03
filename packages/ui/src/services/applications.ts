// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import {
    ApplicationListResponseSchema,
    ApplicationResponseSchema,
    type ApplicationListResponse,
    type ApplicationResponse,
} from '@/schemas/applications';
import type { ApplicationStage } from '@/schemas/enums';

export interface ApplicationsQueryParams {
    sort_by?: 'urgency' | 'updated_at' | 'loan_amount';
    filter_stage?: ApplicationStage;
    filter_stalled?: boolean;
    offset?: number;
    limit?: number;
}

export async function fetchApplications(params?: ApplicationsQueryParams): Promise<ApplicationListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params?.filter_stage) searchParams.set('filter_stage', params.filter_stage);
    if (params?.filter_stalled) searchParams.set('filter_stalled', 'true');
    if (params?.offset != null) searchParams.set('offset', String(params.offset));
    if (params?.limit != null) searchParams.set('limit', String(params.limit));
    const qs = searchParams.toString();
    const data = await apiGet<unknown>(`/api/applications/${qs ? `?${qs}` : ''}`);
    return ApplicationListResponseSchema.parse(data);
}

export async function fetchApplication(id: number): Promise<ApplicationResponse> {
    const data = await apiGet<unknown>(`/api/applications/${id}`);
    return ApplicationResponseSchema.parse(data);
}
