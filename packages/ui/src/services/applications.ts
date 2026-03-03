// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import {
    ApplicationListResponseSchema,
    ApplicationResponseSchema,
    type ApplicationListResponse,
    type ApplicationResponse,
} from '@/schemas/applications';

export async function fetchApplications(): Promise<ApplicationListResponse> {
    const data = await apiGet<unknown>('/api/applications');
    return ApplicationListResponseSchema.parse(data);
}

export async function fetchApplication(id: number): Promise<ApplicationResponse> {
    const data = await apiGet<unknown>(`/api/applications/${id}`);
    return ApplicationResponseSchema.parse(data);
}
