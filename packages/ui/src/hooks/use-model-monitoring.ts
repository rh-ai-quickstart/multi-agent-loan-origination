// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { fetchModelMonitoring } from '@/services/model-monitoring';

export function useModelMonitoring(hours: number) {
    return useQuery({
        queryKey: ['model-monitoring', hours],
        queryFn: () => fetchModelMonitoring(hours),
    });
}
