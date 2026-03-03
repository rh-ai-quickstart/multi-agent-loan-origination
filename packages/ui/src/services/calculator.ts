// This project was developed with assistance from AI tools.

import { apiPost } from '@/lib/api-client';
import {
    AffordabilityResponseSchema,
    type AffordabilityRequest,
    type AffordabilityResponse,
} from '@/schemas/affordability';

export async function calculateAffordability(req: AffordabilityRequest): Promise<AffordabilityResponse> {
    const data = await apiPost<unknown>('/api/public/calculate-affordability', req);
    return AffordabilityResponseSchema.parse(data);
}
