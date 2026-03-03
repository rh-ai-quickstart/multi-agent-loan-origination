// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { fetchApplications, fetchApplication } from '@/services/applications';

export function useApplications() {
    return useQuery({
        queryKey: ['applications'],
        queryFn: fetchApplications,
    });
}

export function useApplication(id: number | undefined) {
    return useQuery({
        queryKey: ['applications', id],
        queryFn: () => fetchApplication(id!),
        enabled: id != null,
    });
}
