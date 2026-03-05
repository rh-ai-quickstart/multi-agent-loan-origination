// This project was developed with assistance from AI tools.

import { useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchConditions, respondToCondition } from '@/services/conditions';

export function useConditions(applicationId: number | undefined) {
    const queryKey = useMemo(() => ['applications', applicationId, 'conditions'] as const, [applicationId]);
    const queryClient = useQueryClient();

    useEffect(() => {
        const handler = () => queryClient.invalidateQueries({ queryKey });
        window.addEventListener('chat-done', handler);
        return () => window.removeEventListener('chat-done', handler);
    }, [queryClient, queryKey]);

    return useQuery({
        queryKey,
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
