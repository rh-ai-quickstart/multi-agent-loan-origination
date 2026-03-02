// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const ApplicationStageSchema = z.enum([
    'INQUIRY',
    'PREQUALIFICATION',
    'APPLICATION',
    'PROCESSING',
    'UNDERWRITING',
    'CONDITIONAL_APPROVAL',
    'CLEAR_TO_CLOSE',
    'CLOSED',
    'DENIED',
    'WITHDRAWN',
]);
export type ApplicationStage = z.infer<typeof ApplicationStageSchema>;

export const APPLICATION_STAGE_LABELS: Record<ApplicationStage, string> = {
    INQUIRY: 'Inquiry',
    PREQUALIFICATION: 'Pre-Qualification',
    APPLICATION: 'Application',
    PROCESSING: 'Processing',
    UNDERWRITING: 'Underwriting',
    CONDITIONAL_APPROVAL: 'Conditional Approval',
    CLEAR_TO_CLOSE: 'Clear to Close',
    CLOSED: 'Closed',
    DENIED: 'Denied',
    WITHDRAWN: 'Withdrawn',
};

export const STAGE_ORDER: ApplicationStage[] = [
    'INQUIRY',
    'PREQUALIFICATION',
    'APPLICATION',
    'PROCESSING',
    'UNDERWRITING',
    'CONDITIONAL_APPROVAL',
    'CLEAR_TO_CLOSE',
    'CLOSED',
];

export const UserRoleSchema = z.enum([
    'ADMIN',
    'PROSPECT',
    'BORROWER',
    'LOAN_OFFICER',
    'UNDERWRITER',
    'CEO',
]);
export type UserRole = z.infer<typeof UserRoleSchema>;

export const LoanTypeSchema = z.enum([
    'CONVENTIONAL_30',
    'CONVENTIONAL_15',
    'FHA',
    'VA',
    'JUMBO',
    'USDA',
    'ARM',
]);
export type LoanType = z.infer<typeof LoanTypeSchema>;

export const LOAN_TYPE_LABELS: Record<LoanType, string> = {
    CONVENTIONAL_30: '30-Year Fixed',
    CONVENTIONAL_15: '15-Year Fixed',
    FHA: 'FHA Loan',
    VA: 'VA Loan',
    JUMBO: 'Jumbo Loan',
    USDA: 'USDA Loan',
    ARM: 'Adjustable-Rate Mortgage',
};

export const DocumentTypeSchema = z.enum([
    'W2',
    'PAY_STUB',
    'TAX_RETURN',
    'BANK_STATEMENT',
    'ID',
    'PROPERTY_APPRAISAL',
    'INSURANCE',
    'OTHER',
]);
export type DocumentType = z.infer<typeof DocumentTypeSchema>;

export const DocumentStatusSchema = z.enum([
    'UPLOADED',
    'PROCESSING',
    'PROCESSING_COMPLETE',
    'PROCESSING_FAILED',
    'PENDING_REVIEW',
    'ACCEPTED',
    'FLAGGED_FOR_RESUBMISSION',
    'REJECTED',
]);
export type DocumentStatus = z.infer<typeof DocumentStatusSchema>;

export const ConditionSeveritySchema = z.enum([
    'PRIOR_TO_APPROVAL',
    'PRIOR_TO_DOCS',
    'PRIOR_TO_CLOSING',
    'PRIOR_TO_FUNDING',
]);
export type ConditionSeverity = z.infer<typeof ConditionSeveritySchema>;

export const ConditionStatusSchema = z.enum([
    'OPEN',
    'RESPONDED',
    'UNDER_REVIEW',
    'CLEARED',
    'WAIVED',
    'ESCALATED',
]);
export type ConditionStatus = z.infer<typeof ConditionStatusSchema>;

export const DecisionTypeSchema = z.enum([
    'APPROVED',
    'CONDITIONAL_APPROVAL',
    'SUSPENDED',
    'DENIED',
]);
export type DecisionType = z.infer<typeof DecisionTypeSchema>;

export const UrgencyLevelSchema = z.enum(['CRITICAL', 'HIGH', 'MEDIUM', 'NORMAL']);
export type UrgencyLevel = z.infer<typeof UrgencyLevelSchema>;

export const RateLockStatusSchema = z.enum(['ACTIVE', 'EXPIRED', 'NONE']);
export type RateLockStatus = z.infer<typeof RateLockStatusSchema>;

export const EmploymentStatusSchema = z.enum([
    'W2_EMPLOYEE',
    'SELF_EMPLOYED',
    'RETIRED',
    'UNEMPLOYED',
    'OTHER',
]);
export type EmploymentStatus = z.infer<typeof EmploymentStatusSchema>;
