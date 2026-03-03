// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const StageInfoSchema = z.object({
    label: z.string(),
    description: z.string(),
    next_step: z.string(),
    typical_timeline: z.string(),
});

export type StageInfo = z.infer<typeof StageInfoSchema>;

export const PendingActionSchema = z.object({
    action_type: z.string(),
    description: z.string(),
});

export type PendingAction = z.infer<typeof PendingActionSchema>;

export const UrgencyIndicatorSchema = z.object({
    level: z.string(),
    factors: z.array(z.string()).optional().default([]),
    days_in_stage: z.number(),
    expected_stage_days: z.number(),
}).nullable().optional();

export const ApplicationStatusResponseSchema = z.object({
    application_id: z.number(),
    stage: z.string(),
    stage_info: StageInfoSchema,
    is_document_complete: z.boolean(),
    provided_doc_count: z.number(),
    required_doc_count: z.number(),
    open_condition_count: z.number(),
    pending_actions: z.array(PendingActionSchema),
    urgency: UrgencyIndicatorSchema,
});

export type ApplicationStatusResponse = z.infer<typeof ApplicationStatusResponseSchema>;
