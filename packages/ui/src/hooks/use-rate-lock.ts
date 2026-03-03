// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { fetchRateLock } from '@/services/rate-lock';

export function useRateLock(applicationId: number | undefined) {
    return useQuery({
        queryKey: ['applications', applicationId, 'rate-lock'],
        queryFn: () => fetchRateLock(applicationId!),
        enabled: applicationId != null,
    });
}
