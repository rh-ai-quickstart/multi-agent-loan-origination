// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import {
    ApplicationStatusResponseSchema,
    type ApplicationStatusResponse,
} from '@/schemas/status';

export async function fetchApplicationStatus(applicationId: number): Promise<ApplicationStatusResponse> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/status`);
    return ApplicationStatusResponseSchema.parse(data);
}
