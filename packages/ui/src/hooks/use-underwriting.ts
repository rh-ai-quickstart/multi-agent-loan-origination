// This project was developed with assistance from AI tools.

import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api-client';
import { fetchRiskAssessment, fetchComplianceResult } from '@/services/underwriting';

function useRefetchOnChatDone(queryKey: readonly unknown[]) {
    const queryClient = useQueryClient();
    useEffect(() => {
        const handler = () => queryClient.invalidateQueries({ queryKey });
        window.addEventListener('chat-done', handler);
        return () => window.removeEventListener('chat-done', handler);
    }, [queryClient, queryKey]);
}

export function useRiskAssessment(applicationId: number | undefined) {
    const queryKey = ['applications', applicationId, 'risk-assessment'] as const;
    useRefetchOnChatDone(queryKey);

    return useQuery({
        queryKey,
        queryFn: () => fetchRiskAssessment(applicationId!),
        enabled: applicationId != null,
        retry: (failureCount, error) => {
            if (error instanceof ApiError && error.status === 404) return false;
            return failureCount < 3;
        },
    });
}

export function useComplianceResult(applicationId: number | undefined) {
    const queryKey = ['applications', applicationId, 'compliance-result'] as const;
    useRefetchOnChatDone(queryKey);

    return useQuery({
        queryKey,
        queryFn: () => fetchComplianceResult(applicationId!),
        enabled: applicationId != null,
        retry: (failureCount, error) => {
            if (error instanceof ApiError && error.status === 404) return false;
            return failureCount < 3;
        },
    });
}
