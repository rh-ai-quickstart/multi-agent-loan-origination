// This project was developed with assistance from AI tools.

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchDocuments, fetchCompleteness, fetchExtractions, uploadDocument, updateDocumentStatus } from '@/services/documents';

const PROCESSING_STATUSES = new Set(['uploaded', 'processing', 'processing_complete']);

export function useDocuments(applicationId: number | undefined) {
    return useQuery({
        queryKey: ['applications', applicationId, 'documents'],
        queryFn: () => fetchDocuments(applicationId!),
        enabled: applicationId != null,
        refetchInterval: (query) => {
            const hasProcessing = query.state.data?.data.some((d) =>
                PROCESSING_STATUSES.has(d.status),
            );
            return hasProcessing ? 3000 : false;
        },
    });
}

export function useCompleteness(applicationId: number | undefined, hasProcessing?: boolean) {
    return useQuery({
        queryKey: ['applications', applicationId, 'documents', 'completeness'],
        queryFn: () => fetchCompleteness(applicationId!),
        enabled: applicationId != null,
        refetchInterval: hasProcessing ? 3000 : false,
    });
}

export function useExtractions(applicationId: number | undefined, documentId: number | undefined) {
    return useQuery({
        queryKey: ['applications', applicationId, 'documents', documentId, 'extractions'],
        queryFn: () => fetchExtractions(applicationId!, documentId!),
        enabled: applicationId != null && documentId != null,
    });
}

export function useUpdateDocumentStatus(applicationId: number | undefined) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ documentId, status, reason }: { documentId: number; status: string; reason?: string }) =>
            updateDocumentStatus(applicationId!, documentId, status, reason),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['applications', applicationId, 'documents'] });
        },
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
