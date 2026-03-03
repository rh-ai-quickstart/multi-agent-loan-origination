// This project was developed with assistance from AI tools.

import { apiGet, apiPost } from '@/lib/api-client';
import {
    ConditionListResponseSchema,
    ConditionSchema,
    type ConditionListResponse,
    type Condition,
} from '@/schemas/conditions';

export async function fetchConditions(applicationId: number): Promise<ConditionListResponse> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/conditions`);
    return ConditionListResponseSchema.parse(data);
}

export async function respondToCondition(
    applicationId: number,
    conditionId: number,
    text: string,
): Promise<Condition> {
    const resp = await apiPost<{ data: unknown }>(
        `/api/applications/${applicationId}/conditions/${conditionId}/respond`,
        { response_text: text },
    );
    return ConditionSchema.parse(resp.data);
}
