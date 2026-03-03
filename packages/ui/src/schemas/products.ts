// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const ProductInfoSchema = z.object({
    id: z.string(),
    name: z.string(),
    description: z.string(),
    min_down_payment_pct: z.number(),
    typical_rate: z.number(),
});

export type ProductInfo = z.infer<typeof ProductInfoSchema>;
