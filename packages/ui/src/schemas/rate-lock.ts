// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const RateLockResponseSchema = z.object({
    application_id: z.number(),
    status: z.string(),
    locked_rate: z.number().nullable().optional(),
    lock_date: z.string().nullable().optional(),
    expiration_date: z.string().nullable().optional(),
    days_remaining: z.number().nullable().optional(),
    is_urgent: z.boolean().nullable().optional(),
});

export type RateLockResponse = z.infer<typeof RateLockResponseSchema>;
