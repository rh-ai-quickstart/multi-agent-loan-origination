// This project was developed with assistance from AI tools.

import { z } from 'zod';
import { ApplicationStageSchema, LoanTypeSchema, EmploymentStatusSchema } from './enums';
import { PaginationSchema } from './pagination';

export const BorrowerSummarySchema = z.object({
    id: z.number(),
    first_name: z.string(),
    last_name: z.string(),
    email: z.string(),
    ssn: z.string().nullable().optional(),
    dob: z.string().nullable().optional(),
    employment_status: EmploymentStatusSchema.nullable().optional(),
    is_primary: z.boolean().optional(),
});

export type BorrowerSummary = z.infer<typeof BorrowerSummarySchema>;

export const UrgencyIndicatorSchema = z.object({
    level: z.string(),
    factors: z.array(z.string()).optional().default([]),
    days_in_stage: z.number(),
    expected_stage_days: z.number(),
}).nullable().optional();

export const ApplicationResponseSchema = z.object({
    id: z.number(),
    stage: ApplicationStageSchema,
    loan_type: LoanTypeSchema.nullable().optional(),
    property_address: z.string().nullable().optional(),
    loan_amount: z.coerce.number().nullable().optional(),
    property_value: z.coerce.number().nullable().optional(),
    assigned_to: z.string().nullable().optional(),
    created_at: z.string(),
    updated_at: z.string(),
    borrowers: z.array(BorrowerSummarySchema).optional().default([]),
    urgency: UrgencyIndicatorSchema,
});

export type ApplicationResponse = z.infer<typeof ApplicationResponseSchema>;

export const ApplicationListResponseSchema = z.object({
    data: z.array(ApplicationResponseSchema),
    pagination: PaginationSchema,
});

export type ApplicationListResponse = z.infer<typeof ApplicationListResponseSchema>;
