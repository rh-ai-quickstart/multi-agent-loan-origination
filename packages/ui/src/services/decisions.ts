// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import {
    DecisionListResponseSchema,
    type DecisionListResponse,
} from '@/schemas/decisions';

export async function fetchDecisions(applicationId: number): Promise<DecisionListResponse> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/decisions`);
    return DecisionListResponseSchema.parse(data);
}
