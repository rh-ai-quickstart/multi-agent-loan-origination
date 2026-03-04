// This project was developed with assistance from AI tools.

import { useQuery } from '@tanstack/react-query';
import { fetchDisclosureStatus } from '@/services/disclosures';

export function useDisclosures(applicationId: number | undefined) {
    return useQuery({
        queryKey: ['applications', applicationId, 'disclosures'],
        queryFn: () => fetchDisclosureStatus(applicationId!),
        enabled: applicationId != null,
    });
}
