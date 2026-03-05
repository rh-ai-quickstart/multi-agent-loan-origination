// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const StageCountSchema = z.object({
    stage: z.string(),
    count: z.number(),
});

export const StageTurnTimeSchema = z.object({
    from_stage: z.string(),
    to_stage: z.string(),
    avg_days: z.number(),
    sample_size: z.number(),
});

export const PipelineSummarySchema = z.object({
    total_applications: z.number(),
    by_stage: z.array(StageCountSchema),
    pull_through_rate: z.number(),
    avg_days_to_close: z.number().nullable().optional(),
    turn_times: z.array(StageTurnTimeSchema),
    time_range_days: z.number(),
    computed_at: z.string(),
});

export type PipelineSummary = z.infer<typeof PipelineSummarySchema>;

export const LOPerformanceRowSchema = z.object({
    lo_id: z.string(),
    lo_name: z.string().nullable().optional(),
    active_count: z.number(),
    closed_count: z.number(),
    pull_through_rate: z.number(),
    avg_days_to_underwriting: z.number().nullable().optional(),
    avg_days_conditions_to_cleared: z.number().nullable().optional(),
    denial_rate: z.number(),
});

export const LOPerformanceSummarySchema = z.object({
    loan_officers: z.array(LOPerformanceRowSchema),
    time_range_days: z.number(),
    computed_at: z.string(),
});

export type LOPerformanceSummary = z.infer<typeof LOPerformanceSummarySchema>;

export const DenialReasonSchema = z.object({
    reason: z.string(),
    count: z.number(),
    percentage: z.number(),
});

export const DenialTrendPointSchema = z.object({
    period: z.string(),
    denial_rate: z.number(),
    denial_count: z.number(),
    total_decided: z.number(),
});

export const DenialTrendsSchema = z.object({
    overall_denial_rate: z.number(),
    total_decisions: z.number(),
    total_denials: z.number(),
    trend: z.array(DenialTrendPointSchema),
    top_reasons: z.array(DenialReasonSchema),
    by_product: z.record(z.string(), z.number()).nullable().optional(),
    time_range_days: z.number(),
    computed_at: z.string(),
});

export type DenialTrends = z.infer<typeof DenialTrendsSchema>;
