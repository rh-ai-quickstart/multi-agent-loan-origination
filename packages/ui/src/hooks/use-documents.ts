// This project was developed with assistance from AI tools.

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchDocuments, fetchCompleteness, uploadDocument } from '@/services/documents';

export function useDocuments(applicationId: number | undefined) {
    return useQuery({
        queryKey: ['applications', applicationId, 'documents'],
        queryFn: () => fetchDocuments(applicationId!),
        enabled: applicationId != null,
    });
}

export function useCompleteness(applicationId: number | undefined) {
    return useQuery({
        queryKey: ['applications', applicationId, 'documents', 'completeness'],
        queryFn: () => fetchCompleteness(applicationId!),
        enabled: applicationId != null,
    });
}

export function useUploadDocument(applicationId: number | undefined) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ file, documentType }: { file: File; documentType: string }) =>
            uploadDocument(applicationId!, file, documentType),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['applications', applicationId, 'documents'] });
        },
    });
}
