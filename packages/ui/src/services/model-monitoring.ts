// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import {
    ModelMonitoringSummarySchema,
    type ModelMonitoringSummary,
} from '@/schemas/model-monitoring';

export async function fetchModelMonitoring(hours: number): Promise<ModelMonitoringSummary> {
    const data = await apiGet<unknown>(`/api/analytics/model-monitoring?hours=${hours}`);
    return ModelMonitoringSummarySchema.parse(data);
}
