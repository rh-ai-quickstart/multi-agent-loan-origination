// This project was developed with assistance from AI tools.

import { apiGet, apiFetch } from '@/lib/api-client';
import {
    DocumentListResponseSchema,
    CompletenessResponseSchema,
    ExtractionListResponseSchema,
    type DocumentListResponse,
    type CompletenessResponse,
    type ExtractionListResponse,
    type Document,
} from '@/schemas/documents';
import { DocumentSchema } from '@/schemas/documents';

export async function fetchDocuments(applicationId: number): Promise<DocumentListResponse> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/documents`);
    return DocumentListResponseSchema.parse(data);
}

export async function fetchCompleteness(applicationId: number): Promise<CompletenessResponse> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/completeness`);
    return CompletenessResponseSchema.parse(data);
}

export async function fetchExtractions(applicationId: number, documentId: number): Promise<ExtractionListResponse> {
    const data = await apiGet<unknown>(`/api/applications/${applicationId}/documents/${documentId}/extractions`);
    return ExtractionListResponseSchema.parse(data);
}

export async function updateDocumentStatus(
    applicationId: number,
    documentId: number,
    status: string,
    reason?: string,
): Promise<Document> {
    const data = await apiFetch<unknown>(`/api/applications/${applicationId}/documents/${documentId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, reason }),
    });
    return DocumentSchema.parse(data);
}

export async function uploadDocument(
    applicationId: number,
    file: File,
    documentType: string,
): Promise<Document> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('doc_type', documentType);
    const data = await apiFetch<unknown>(`/api/applications/${applicationId}/documents`, {
        method: 'POST',
        body: formData,
    });
    return DocumentSchema.parse(data);
}
