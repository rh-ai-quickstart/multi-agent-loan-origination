// This project was developed with assistance from AI tools.

import { z } from 'zod';
import { apiGet } from '@/lib/api-client';
import { ProductInfoSchema, type ProductInfo } from '@/schemas/products';

export async function fetchProducts(): Promise<ProductInfo[]> {
    const data = await apiGet<unknown>('/api/public/products');
    return z.array(ProductInfoSchema).parse(data);
}
