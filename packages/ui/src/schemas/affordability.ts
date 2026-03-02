// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const AffordabilityRequestSchema = z.object({
    gross_annual_income: z.number(),
    monthly_debts: z.number(),
    down_payment: z.number(),
    interest_rate: z.number().optional(),
    loan_term_years: z.number().optional(),
});

export const AffordabilityResponseSchema = z.object({
    max_loan_amount: z.number(),
    estimated_monthly_payment: z.number(),
    estimated_purchase_price: z.number(),
    dti_ratio: z.number(),
    dti_warning: z.string().nullable().optional(),
    pmi_warning: z.string().nullable().optional(),
});

export type AffordabilityRequest = z.infer<typeof AffordabilityRequestSchema>;
export type AffordabilityResponse = z.infer<typeof AffordabilityResponseSchema>;
