// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const DisclosureItemSchema = z.object({
    id: z.string(),
    label: z.string(),
    summary: z.string(),
    acknowledged: z.boolean(),
});

export type DisclosureItem = z.infer<typeof DisclosureItemSchema>;

export const DisclosureStatusResponseSchema = z.object({
    application_id: z.number(),
    all_acknowledged: z.boolean(),
    disclosures: z.array(DisclosureItemSchema),
});

export type DisclosureStatusResponse = z.infer<typeof DisclosureStatusResponseSchema>;
