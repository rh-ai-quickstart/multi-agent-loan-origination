// This project was developed with assistance from AI tools.

import { z } from 'zod';
import { ConditionSeveritySchema, ConditionStatusSchema } from './enums';
import { PaginationSchema } from './pagination';

export const ConditionSchema = z.object({
    id: z.number(),
    description: z.string(),
    severity: ConditionSeveritySchema.nullable().optional(),
    status: ConditionStatusSchema.nullable().optional(),
    response_text: z.string().nullable().optional(),
    issued_by: z.string().nullable().optional(),
    cleared_by: z.string().nullable().optional(),
    due_date: z.string().nullable().optional(),
    iteration_count: z.number().optional().default(0),
    waiver_rationale: z.string().nullable().optional(),
    created_at: z.string().nullable().optional(),
});

export type Condition = z.infer<typeof ConditionSchema>;

export const ConditionListResponseSchema = z.object({
    data: z.array(ConditionSchema),
    pagination: PaginationSchema,
});

export type ConditionListResponse = z.infer<typeof ConditionListResponseSchema>;
