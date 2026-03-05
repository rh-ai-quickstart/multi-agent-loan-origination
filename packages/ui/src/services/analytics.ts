// This project was developed with assistance from AI tools.

import { apiGet } from '@/lib/api-client';
import {
    PipelineSummarySchema,
    DenialTrendsSchema,
    LOPerformanceSummarySchema,
    type PipelineSummary,
    type DenialTrends,
    type LOPerformanceSummary,
} from '@/schemas/analytics';

export async function fetchPipelineSummary(days: number): Promise<PipelineSummary> {
    const data = await apiGet<unknown>(`/api/analytics/pipeline?days=${days}`);
    return PipelineSummarySchema.parse(data);
}

export async function fetchDenialTrends(days: number): Promise<DenialTrends> {
    const data = await apiGet<unknown>(`/api/analytics/denial-trends?days=${days}`);
    return DenialTrendsSchema.parse(data);
}

export async function fetchLOPerformance(days: number): Promise<LOPerformanceSummary> {
    const data = await apiGet<unknown>(`/api/analytics/lo-performance?days=${days}`);
    return LOPerformanceSummarySchema.parse(data);
}
