// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { fetchApplicationStatus } from '@/services/status';

export function useApplicationStatus(applicationId: number | undefined) {
    return useQuery({
        queryKey: ['applications', applicationId, 'status'],
        queryFn: () => fetchApplicationStatus(applicationId!),
        enabled: applicationId != null,
    });
}
