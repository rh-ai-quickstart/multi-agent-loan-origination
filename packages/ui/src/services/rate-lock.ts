// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import { RateLockResponseSchema, type RateLockResponse } from '@/schemas/rate-lock';

export async function fetchRateLock(applicationId: number): Promise<RateLockResponse> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/rate-lock`);
    return RateLockResponseSchema.parse(data);
}
