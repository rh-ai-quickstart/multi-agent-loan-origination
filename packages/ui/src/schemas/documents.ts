// This project was developed with assistance from AI tools.

import { z } from 'zod';
import { DocumentTypeSchema, DocumentStatusSchema } from './enums';
import { PaginationSchema } from './pagination';

export const DocumentSchema = z.object({
    id: z.number(),
    application_id: z.number(),
    borrower_id: z.number().nullable().optional(),
    doc_type: DocumentTypeSchema,
    status: DocumentStatusSchema,
    quality_flags: z.string().nullable().optional(),
    uploaded_by: z.string().nullable().optional(),
    created_at: z.string(),
    updated_at: z.string(),
});

export type Document = z.infer<typeof DocumentSchema>;

export const DocumentListResponseSchema = z.object({
    data: z.array(DocumentSchema),
    pagination: PaginationSchema,
});

export type DocumentListResponse = z.infer<typeof DocumentListResponseSchema>;

export const DocumentRequirementSchema = z.object({
    doc_type: DocumentTypeSchema,
    label: z.string(),
    is_provided: z.boolean(),
    document_id: z.number().nullable().optional(),
    status: DocumentStatusSchema.nullable().optional(),
    quality_flags: z.array(z.string()).optional().default([]),
});

export type DocumentRequirement = z.infer<typeof DocumentRequirementSchema>;

export const CompletenessResponseSchema = z.object({
    application_id: z.number(),
    is_complete: z.boolean(),
    requirements: z.array(DocumentRequirementSchema),
    provided_count: z.number(),
    required_count: z.number(),
});

export type CompletenessResponse = z.infer<typeof CompletenessResponseSchema>;

export const ExtractionFieldSchema = z.object({
    id: z.number(),
    field_name: z.string(),
    field_value: z.string().nullable().optional(),
    confidence: z.number().nullable().optional(),
    source_page: z.number().nullable().optional(),
});

export type ExtractionField = z.infer<typeof ExtractionFieldSchema>;

export const ExtractionListResponseSchema = z.object({
    document_id: z.number(),
    extractions: z.array(ExtractionFieldSchema),
});

export type ExtractionListResponse = z.infer<typeof ExtractionListResponseSchema>;
