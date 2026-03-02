// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { fetchProducts } from '@/services/products';

export function useProducts() {
    return useQuery({
        queryKey: ['products'],
        queryFn: fetchProducts,
    });
}
