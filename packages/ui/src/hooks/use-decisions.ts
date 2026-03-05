// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { fetchDecisions } from '@/services/decisions';

export function useDecisions(applicationId: number | undefined) {
    return useQuery({
        queryKey: ['applications', applicationId, 'decisions'],
        queryFn: () => fetchDecisions(applicationId!),
        enabled: applicationId != null,
    });
}
