// This project was developed with assistance from AI tools.

import { z } from 'zod';
import { DecisionTypeSchema } from './enums';
import { PaginationSchema } from './pagination';

export const DecisionItemSchema = z.object({
    id: z.number(),
    application_id: z.number(),
    decision_type: DecisionTypeSchema,
    rationale: z.string().nullable().optional(),
    ai_recommendation: z.string().nullable().optional(),
    ai_agreement: z.boolean().nullable().optional(),
    override_rationale: z.string().nullable().optional(),
    denial_reasons: z.array(z.string()).nullable().optional(),
    credit_score_used: z.number().nullable().optional(),
    credit_score_source: z.string().nullable().optional(),
    contributing_factors: z.string().nullable().optional(),
    decided_by: z.string().nullable().optional(),
    created_at: z.string().nullable().optional(),
});

export type DecisionItem = z.infer<typeof DecisionItemSchema>;

export const DecisionListResponseSchema = z.object({
    data: z.array(DecisionItemSchema),
    pagination: PaginationSchema,
});

export type DecisionListResponse = z.infer<typeof DecisionListResponseSchema>;
