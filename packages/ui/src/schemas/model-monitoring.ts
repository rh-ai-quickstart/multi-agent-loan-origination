// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const LatencyMetricsSchema = z.object({
    p50_ms: z.number(),
    p95_ms: z.number(),
    p99_ms: z.number(),
    trend: z.array(z.object({
        timestamp: z.string(),
        p50_ms: z.number(),
        p95_ms: z.number(),
        p99_ms: z.number(),
    })).default([]),
    by_model: z.array(z.object({
        model: z.string(),
        p50_ms: z.number(),
        p95_ms: z.number(),
        p99_ms: z.number(),
        call_count: z.number(),
    })).default([]),
});

export const TokenUsageSchema = z.object({
    input_tokens: z.number(),
    output_tokens: z.number(),
    total_tokens: z.number(),
    trend: z.array(z.object({
        timestamp: z.string(),
        input_tokens: z.number(),
        output_tokens: z.number(),
        total_tokens: z.number(),
    })).default([]),
    by_model: z.array(z.object({
        model: z.string(),
        input_tokens: z.number(),
        output_tokens: z.number(),
        total_tokens: z.number(),
        call_count: z.number(),
    })).default([]),
});

export const ErrorMetricsSchema = z.object({
    total_calls: z.number(),
    error_count: z.number(),
    error_rate: z.number(),
    top_errors: z.array(z.object({
        error_type: z.string(),
        count: z.number(),
    })).default([]),
    trend: z.array(z.object({
        timestamp: z.string(),
        total_calls: z.number(),
        error_count: z.number(),
        error_rate: z.number(),
    })).default([]),
});

export const RoutingDistributionSchema = z.object({
    models: z.array(z.object({
        model: z.string(),
        call_count: z.number(),
        percentage: z.number(),
    })).default([]),
    total_calls: z.number(),
});

export const ModelMonitoringSummarySchema = z.object({
    langfuse_available: z.boolean(),
    latency: LatencyMetricsSchema.nullable().optional(),
    token_usage: TokenUsageSchema.nullable().optional(),
    errors: ErrorMetricsSchema.nullable().optional(),
    routing: RoutingDistributionSchema.nullable().optional(),
    time_range_hours: z.number(),
    computed_at: z.string(),
});

export type ModelMonitoringSummary = z.infer<typeof ModelMonitoringSummarySchema>;
