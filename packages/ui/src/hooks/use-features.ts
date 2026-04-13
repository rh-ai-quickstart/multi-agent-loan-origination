// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { getFeatures } from '@/services/features';

export function useFeatures() {
    return useQuery({
        queryKey: ['features'],
        queryFn: getFeatures,
        staleTime: Infinity,
    });
}
