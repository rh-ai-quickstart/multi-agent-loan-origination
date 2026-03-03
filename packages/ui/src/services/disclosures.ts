// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import { DisclosureStatusResponseSchema, type DisclosureStatusResponse } from '@/schemas/disclosures';

export async function fetchDisclosureStatus(applicationId: number): Promise<DisclosureStatusResponse> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/disclosures`);
    return DisclosureStatusResponseSchema.parse(data);
}
