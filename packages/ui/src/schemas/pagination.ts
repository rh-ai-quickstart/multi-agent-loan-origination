// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const PaginationSchema = z.object({
    total: z.number(),
    offset: z.number(),
    limit: z.number(),
    has_more: z.boolean(),
});

export type Pagination = z.infer<typeof PaginationSchema>;
