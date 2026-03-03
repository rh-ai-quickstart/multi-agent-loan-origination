// This project was developed with assistance from AI tools.

import { apiGet, apiFetch } from '@/lib/api-client';
import {
    DocumentListResponseSchema,
    CompletenessResponseSchema,
    type DocumentListResponse,
    type CompletenessResponse,
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
