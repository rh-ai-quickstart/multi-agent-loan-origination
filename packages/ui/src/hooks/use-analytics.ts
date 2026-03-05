// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { fetchPipelineSummary, fetchDenialTrends, fetchLOPerformance } from '@/services/analytics';

export function usePipelineSummary(days: number) {
    return useQuery({
        queryKey: ['analytics', 'pipeline', days],
        queryFn: () => fetchPipelineSummary(days),
    });
}

export function useDenialTrends(days: number) {
    return useQuery({
        queryKey: ['analytics', 'denial-trends', days],
        queryFn: () => fetchDenialTrends(days),
    });
}

export function useLOPerformance(days: number) {
    return useQuery({
        queryKey: ['analytics', 'lo-performance', days],
        queryFn: () => fetchLOPerformance(days),
    });
}
