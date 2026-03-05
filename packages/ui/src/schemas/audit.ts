// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const AuditEventItemSchema = z.object({
    id: z.number(),
    timestamp: z.string(),
    event_type: z.string(),
    user_id: z.string().nullable().optional(),
    user_role: z.string().nullable().optional(),
    application_id: z.number().nullable().optional(),
    decision_id: z.number().nullable().optional(),
    event_data: z.record(z.string(), z.unknown()).nullable().optional(),
});

export type AuditEventItem = z.infer<typeof AuditEventItemSchema>;

export const AuditSearchResponseSchema = z.object({
    count: z.number(),
    events: z.array(AuditEventItemSchema),
});

export type AuditSearchResponse = z.infer<typeof AuditSearchResponseSchema>;
