// This project was developed with assistance from AI tools.

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchConditions, respondToCondition } from '@/services/conditions';

export function useConditions(applicationId: number | undefined) {
    return useQuery({
        queryKey: ['applications', applicationId, 'conditions'],
        queryFn: () => fetchConditions(applicationId!),
        enabled: applicationId != null,
    });
}

export function useRespondToCondition(applicationId: number | undefined) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ conditionId, text }: { conditionId: number; text: string }) =>
            respondToCondition(applicationId!, conditionId, text),
        onSuccess: () => {
            queryClient.invalidateQueries({
                queryKey: ['applications', applicationId, 'conditions'],
            });
        },
    });
}
