// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const ApplicationStageSchema = z.enum([
    'inquiry',
    'prequalification',
    'application',
    'processing',
    'underwriting',
    'conditional_approval',
    'clear_to_close',
    'closed',
    'denied',
    'withdrawn',
]);
export type ApplicationStage = z.infer<typeof ApplicationStageSchema>;

export const APPLICATION_STAGE_LABELS: Record<ApplicationStage, string> = {
    inquiry: 'Inquiry',
    prequalification: 'Pre-Qualification',
    application: 'Application',
    processing: 'Processing',
    underwriting: 'Underwriting',
    conditional_approval: 'Decision',
    clear_to_close: 'Clear to Close',
    closed: 'Closed',
    denied: 'Denied',
    withdrawn: 'Withdrawn',
};

export const STAGE_ORDER: ApplicationStage[] = [
    'inquiry',
    'prequalification',
    'application',
    'processing',
    'underwriting',
    'conditional_approval',
    'clear_to_close',
    'closed',
];

export const UserRoleSchema = z.enum([
    'admin',
    'prospect',
    'borrower',
    'loan_officer',
    'underwriter',
    'ceo',
]);
export type UserRole = z.infer<typeof UserRoleSchema>;

export const LoanTypeSchema = z.enum([
    'conventional_30',
    'conventional_15',
    'fha',
    'va',
    'jumbo',
    'usda',
    'arm',
]);
export type LoanType = z.infer<typeof LoanTypeSchema>;

export const LOAN_TYPE_LABELS: Record<LoanType, string> = {
    conventional_30: '30-Year Fixed',
    conventional_15: '15-Year Fixed',
    fha: 'FHA Loan',
    va: 'VA Loan',
    jumbo: 'Jumbo Loan',
    usda: 'USDA Loan',
    arm: 'Adjustable-Rate Mortgage',
};

export const DocumentTypeSchema = z.enum([
    'w2',
    'pay_stub',
    'tax_return',
    'bank_statement',
    'drivers_license',
    'passport',
    'property_appraisal',
    'homeowners_insurance',
    'title_insurance',
    'flood_insurance',
    'purchase_agreement',
    'gift_letter',
    'other',
]);
export type DocumentType = z.infer<typeof DocumentTypeSchema>;

export const DocumentStatusSchema = z.enum([
    'uploaded',
    'processing',
    'processing_complete',
    'processing_failed',
    'pending_review',
    'accepted',
    'flagged_for_resubmission',
    'rejected',
]);
export type DocumentStatus = z.infer<typeof DocumentStatusSchema>;

export const ConditionSeveritySchema = z.enum([
    'prior_to_approval',
    'prior_to_docs',
    'prior_to_closing',
    'prior_to_funding',
]);
export type ConditionSeverity = z.infer<typeof ConditionSeveritySchema>;

export const ConditionStatusSchema = z.enum([
    'open',
    'responded',
    'under_review',
    'cleared',
    'waived',
    'escalated',
]);
export type ConditionStatus = z.infer<typeof ConditionStatusSchema>;

export const DecisionTypeSchema = z.enum([
    'approved',
    'conditional_approval',
    'suspended',
    'denied',
]);
export type DecisionType = z.infer<typeof DecisionTypeSchema>;

export const UrgencyLevelSchema = z.enum(['critical', 'high', 'medium', 'normal']);
export type UrgencyLevel = z.infer<typeof UrgencyLevelSchema>;

export const RateLockStatusSchema = z.enum(['active', 'expired', 'none']);
export type RateLockStatus = z.infer<typeof RateLockStatusSchema>;

export const EmploymentStatusSchema = z.enum([
    'w2_employee',
    'self_employed',
    'retired',
    'unemployed',
    'other',
]);
export type EmploymentStatus = z.infer<typeof EmploymentStatusSchema>;
