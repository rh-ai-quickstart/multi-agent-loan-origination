// This project was developed with assistance from AI tools.

import React, { useState, useRef } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import {
    ChevronRight,
    FileText,
    Lock,
    User,
    DollarSign,
    Home,
    MapPin,
    Briefcase,
    Send,
    Upload,
    AlertTriangle,
    CheckCircle2,
    ClipboardList,
} from 'lucide-react';
import { useApplication } from '@/hooks/use-applications';
import { useDocuments, useCompleteness, useExtractions, useUploadDocument } from '@/hooks/use-documents';
import { useConditions } from '@/hooks/use-conditions';
import { useRateLock } from '@/hooks/use-rate-lock';
import { formatCurrency, formatDate, formatPercent } from '@/lib/format';
import {
    APPLICATION_STAGE_LABELS,
    LOAN_TYPE_LABELS,
} from '@/schemas/enums';
import type { ApplicationResponse } from '@/schemas/applications';
import type { RateLockResponse } from '@/schemas/rate-lock';
import type { Condition } from '@/schemas/conditions';
import { cn } from '@/lib/utils';
import { DOC_TYPE_LABELS, STAGE_BADGE } from '@/lib/labels';

export const Route = createFileRoute('/_authenticated/loan-officer/$applicationId')({
    component: LoanDetail,
});

// -- Helpers ------------------------------------------------------------------

const DOC_STATUS_COLORS: Record<string, string> = {
    uploaded: 'bg-blue-100 text-blue-700',
    processing: 'bg-blue-100 text-blue-700',
    processing_complete: 'bg-blue-100 text-blue-700',
    accepted: 'bg-emerald-100 text-emerald-700',
    pending_review: 'bg-amber-100 text-amber-700',
    flagged_for_resubmission: 'bg-red-100 text-red-700',
    rejected: 'bg-red-100 text-red-700',
    processing_failed: 'bg-red-100 text-red-700',
};

const SEVERITY_COLORS: Record<string, string> = {
    prior_to_approval: 'bg-red-100 text-red-700',
    prior_to_docs: 'bg-orange-100 text-orange-700',
    prior_to_closing: 'bg-amber-100 text-amber-700',
    prior_to_funding: 'bg-blue-100 text-blue-700',
};

const CONDITION_STATUS_COLORS: Record<string, string> = {
    open: 'bg-amber-100 text-amber-700',
    responded: 'bg-blue-100 text-blue-700',
    under_review: 'bg-violet-100 text-violet-700',
    cleared: 'bg-emerald-100 text-emerald-700',
    waived: 'bg-slate-100 text-slate-600',
    escalated: 'bg-red-100 text-red-700',
};

function chatPrefill(message: string, autoSend = true) {
    window.dispatchEvent(
        new CustomEvent('chat-prefill', { detail: { message, autoSend } }),
    );
}

function Skeleton({ className }: { className?: string }) {
    return <div className={cn('animate-pulse rounded-md bg-slate-200 dark:bg-slate-700', className)} />;
}

function CardShell({ children, className }: { children: React.ReactNode; className?: string }) {
    return (
        <div className={cn('rounded-xl border border-border bg-white p-6 shadow-sm dark:bg-slate-900', className)}>
            {children}
        </div>
    );
}

function borrowerName(app: ApplicationResponse): string {
    const primary = app.borrowers?.find((b) => b.is_primary) ?? app.borrowers?.[0];
    if (!primary) return `Application #${app.id}`;
    return `${primary.first_name} ${primary.last_name}`;
}

function initials(app: ApplicationResponse): string {
    const primary = app.borrowers?.find((b) => b.is_primary) ?? app.borrowers?.[0];
    if (!primary) return '?';
    return `${primary.first_name[0] ?? ''}${primary.last_name[0] ?? ''}`.toUpperCase();
}

// -- Tab definitions ----------------------------------------------------------

type Tab = 'profile' | 'financial' | 'documents' | 'conditions';

const TABS: { id: Tab; label: string; icon: typeof User }[] = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'financial', label: 'Financial Summary', icon: DollarSign },
    { id: 'documents', label: 'Documents', icon: FileText },
    { id: 'conditions', label: 'Conditions', icon: ClipboardList },
];

// -- Detail header ------------------------------------------------------------

function DetailHeader({ app, rateLock }: { app: ApplicationResponse; rateLock: RateLockResponse | undefined }) {
    const name = borrowerName(app);
    const ini = initials(app);
    const loanType = app.loan_type ? LOAN_TYPE_LABELS[app.loan_type] : null;

    const rateLockActive = rateLock && rateLock.status === 'active';
    const rateLockExpired = rateLock && rateLock.status === 'expired';

    return (
        <CardShell>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#1e3a5f] text-sm font-bold text-white">
                        {ini}
                    </div>
                    <div>
                        <div className="flex flex-wrap items-center gap-2">
                            <h1 className="text-xl font-bold text-foreground">{name}</h1>
                            <span className="text-sm text-muted-foreground">#{app.id}</span>
                            <span
                                className={cn(
                                    'rounded-full px-2.5 py-0.5 text-xs font-medium',
                                    STAGE_BADGE[app.stage] ?? STAGE_BADGE.inquiry,
                                )}
                            >
                                {APPLICATION_STAGE_LABELS[app.stage]}
                            </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                            <span className="font-semibold text-foreground">{formatCurrency(app.loan_amount)}</span>
                            {app.property_address && (
                                <>
                                    <span>&middot;</span>
                                    <span className="flex items-center gap-1">
                                        <MapPin className="h-3 w-3" />
                                        {app.property_address}
                                    </span>
                                </>
                            )}
                            {loanType && (
                                <>
                                    <span>&middot;</span>
                                    <span>{loanType}</span>
                                </>
                            )}
                            {rateLockActive && rateLock.locked_rate != null && (
                                <>
                                    <span>&middot;</span>
                                    <span className="flex items-center gap-1 text-emerald-600">
                                        <Lock className="h-3 w-3" />
                                        {formatPercent(rateLock.locked_rate / 100)} locked
                                        {rateLock.days_remaining != null && ` (${rateLock.days_remaining}d remaining)`}
                                    </span>
                                </>
                            )}
                            {rateLockExpired && (
                                <>
                                    <span>&middot;</span>
                                    <span className="flex items-center gap-1 text-red-600">
                                        <Lock className="h-3 w-3" /> Rate lock expired
                                    </span>
                                </>
                            )}
                        </div>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => chatPrefill(`Please request any missing documents for application #${app.id}.`)}
                        className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-slate-50 dark:hover:bg-slate-800"
                    >
                        <Upload className="h-4 w-4" />
                        Request Documents
                    </button>
                    <button
                        onClick={() => chatPrefill(`Submit application #${app.id} to underwriting.`)}
                        className="flex items-center gap-1.5 rounded-lg bg-[#1e3a5f] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[#152e42]"
                    >
                        <Send className="h-4 w-4" />
                        Submit to Underwriting
                    </button>
                </div>
            </div>
        </CardShell>
    );
}

// -- Profile tab --------------------------------------------------------------

function ProfileTab({ app }: { app: ApplicationResponse }) {
    const primary = app.borrowers?.find((b) => b.is_primary) ?? app.borrowers?.[0];
    const coborrowers = app.borrowers?.filter((b) => !b.is_primary) ?? [];

    return (
        <div className="grid gap-6 lg:grid-cols-2">
            <CardShell>
                <h3 className="mb-4 text-base font-semibold text-foreground flex items-center gap-2">
                    <User className="h-4 w-4 text-muted-foreground" />
                    Borrower Info
                </h3>
                {primary ? (
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <p className="text-muted-foreground">Name</p>
                            <p className="font-medium text-foreground">{primary.first_name} {primary.last_name}</p>
                        </div>
                        <div className="min-w-0">
                            <p className="text-muted-foreground">Email</p>
                            <p className="truncate font-medium text-foreground" title={primary.email}>{primary.email}</p>
                        </div>
                        {primary.employment_status && (
                            <div>
                                <p className="text-muted-foreground">Employment</p>
                                <p className="font-medium text-foreground capitalize">{primary.employment_status.replace(/_/g, ' ')}</p>
                            </div>
                        )}
                        {primary.dob && (
                            <div>
                                <p className="text-muted-foreground">Date of Birth</p>
                                <p className="font-medium text-foreground">{formatDate(primary.dob)}</p>
                            </div>
                        )}
                    </div>
                ) : (
                    <p className="text-sm text-muted-foreground">No borrower information available.</p>
                )}
                {coborrowers.length > 0 && (
                    <div className="mt-4 border-t border-border pt-4">
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Co-Borrowers</p>
                        {coborrowers.map((cb) => (
                            <div key={cb.id} className="flex items-center gap-2 text-sm">
                                <span className="font-medium text-foreground">{cb.first_name} {cb.last_name}</span>
                                <span className="text-muted-foreground">{cb.email}</span>
                            </div>
                        ))}
                    </div>
                )}
            </CardShell>

            <div className="flex flex-col gap-6">
                <CardShell>
                    <h3 className="mb-4 text-base font-semibold text-foreground flex items-center gap-2">
                        <Home className="h-4 w-4 text-muted-foreground" />
                        Property Info
                    </h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="col-span-2">
                            <p className="text-muted-foreground">Address</p>
                            <p className="font-medium text-foreground">{app.property_address ?? '--'}</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground">Property Value</p>
                            <p className="font-medium text-foreground">{formatCurrency(app.property_value)}</p>
                        </div>
                        {app.loan_amount && app.property_value ? (
                            <div>
                                <p className="text-muted-foreground">LTV</p>
                                <p className="font-medium text-foreground">
                                    {formatPercent(app.loan_amount / app.property_value)}
                                </p>
                            </div>
                        ) : null}
                    </div>
                </CardShell>

                <CardShell>
                    <h3 className="mb-4 text-base font-semibold text-foreground flex items-center gap-2">
                        <Briefcase className="h-4 w-4 text-muted-foreground" />
                        Loan Details
                    </h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <p className="text-muted-foreground">Loan Amount</p>
                            <p className="font-medium text-foreground">{formatCurrency(app.loan_amount)}</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground">Loan Type</p>
                            <p className="font-medium text-foreground">
                                {app.loan_type ? LOAN_TYPE_LABELS[app.loan_type] : '--'}
                            </p>
                        </div>
                        <div>
                            <p className="text-muted-foreground">Application Date</p>
                            <p className="font-medium text-foreground">{formatDate(app.created_at)}</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground">Last Updated</p>
                            <p className="font-medium text-foreground">{formatDate(app.updated_at)}</p>
                        </div>
                    </div>
                </CardShell>
            </div>
        </div>
    );
}

// -- Financial summary tab ----------------------------------------------------

function FinancialSummaryTab({ app }: { app: ApplicationResponse }) {
    return (
        <CardShell>
            <h3 className="mb-4 text-base font-semibold text-foreground">Loan Overview</h3>
            <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
                <div>
                    <p className="text-muted-foreground">Loan Amount</p>
                    <p className="text-lg font-bold text-foreground">{formatCurrency(app.loan_amount)}</p>
                </div>
                <div>
                    <p className="text-muted-foreground">Property Value</p>
                    <p className="text-lg font-bold text-foreground">{formatCurrency(app.property_value)}</p>
                </div>
                {app.loan_amount && app.property_value ? (
                    <>
                        <div>
                            <p className="text-muted-foreground">LTV Ratio</p>
                            <p className="text-lg font-bold text-foreground">
                                {formatPercent(app.loan_amount / app.property_value)}
                            </p>
                        </div>
                        <div>
                            <p className="text-muted-foreground">Down Payment</p>
                            <p className="text-lg font-bold text-foreground">
                                {formatCurrency(app.property_value - app.loan_amount)}
                            </p>
                        </div>
                    </>
                ) : null}
            </div>
        </CardShell>
    );
}

// -- Documents tab ------------------------------------------------------------

function DocumentUpload({ appId }: { appId: number }) {
    const fileRef = useRef<HTMLInputElement>(null);
    const upload = useUploadDocument(appId);

    const handleFiles = (files: FileList | null) => {
        const file = files?.[0];
        if (!file) return;
        upload.mutate(
            { file, documentType: 'other' },
            { onSuccess: () => { if (fileRef.current) fileRef.current.value = ''; } },
        );
    };

    return (
        <CardShell>
            <div
                onClick={() => fileRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                onDrop={(e) => { e.preventDefault(); e.stopPropagation(); handleFiles(e.dataTransfer.files); }}
                className={cn(
                    'flex cursor-pointer items-center justify-center rounded-lg border-2 border-dashed py-6 transition-colors',
                    upload.isPending
                        ? 'border-[#1e3a5f]/30 bg-[#1e3a5f]/5'
                        : 'border-slate-200 hover:border-[#1e3a5f]/40 hover:bg-slate-50 dark:border-slate-700 dark:hover:border-slate-500 dark:hover:bg-slate-800/50',
                )}
            >
                <input
                    ref={fileRef}
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    className="hidden"
                    onChange={(e) => handleFiles(e.target.files)}
                />
                <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Upload className="h-6 w-6" />
                    <p className="text-sm">{upload.isPending ? 'Uploading...' : 'Drop files here or click to upload'}</p>
                </div>
            </div>
            {upload.isError && (
                <p className="mt-2 text-sm text-red-600">Upload failed. Please try again.</p>
            )}
        </CardShell>
    );
}

function ExtractionDetails({ appId, documentId }: { appId: number; documentId: number }) {
    const { data, isLoading } = useExtractions(appId, documentId);

    if (isLoading) return <Skeleton className="h-8 w-full" />;
    if (!data || data.extractions.length === 0) {
        return <p className="text-xs text-muted-foreground italic">No extraction data available.</p>;
    }

    return (
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
            {data.extractions.map((ext) => (
                <div key={ext.id} className="flex items-baseline gap-1.5">
                    <span className="text-muted-foreground">{ext.field_name.replace(/_/g, ' ')}:</span>
                    <span className="font-medium text-foreground">{ext.field_value ?? '--'}</span>
                    {ext.confidence != null && (
                        <span className={cn(
                            'text-[10px]',
                            ext.confidence >= 0.9 ? 'text-emerald-600' : ext.confidence >= 0.7 ? 'text-amber-600' : 'text-red-600',
                        )}>
                            {Math.round(ext.confidence * 100)}%
                        </span>
                    )}
                </div>
            ))}
        </div>
    );
}

function DocumentsTab({ appId }: { appId: number }) {
    const [expandedDocId, setExpandedDocId] = useState<number | null>(null);
    const { data: documents, isLoading: docsLoading } = useDocuments(appId);
    const { data: completeness, isLoading: compLoading } = useCompleteness(appId);

    if (docsLoading || compLoading) {
        return (
            <CardShell>
                <Skeleton className="mb-4 h-6 w-32" />
                <Skeleton className="mb-2 h-10 w-full" />
                <Skeleton className="mb-2 h-10 w-full" />
                <Skeleton className="h-10 w-full" />
            </CardShell>
        );
    }

    const missingDocs = completeness?.requirements.filter((r) => !r.is_provided) ?? [];

    return (
        <div className="flex flex-col gap-6">
            {/* Completeness summary */}
            {completeness && (
                <CardShell>
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-base font-semibold text-foreground">Document Completeness</h3>
                            <p className="mt-1 text-sm text-muted-foreground">
                                {completeness.provided_count} of {completeness.required_count} required documents provided
                            </p>
                        </div>
                        {completeness.is_complete ? (
                            <span className="flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">
                                <CheckCircle2 className="h-3.5 w-3.5" /> Complete
                            </span>
                        ) : (
                            <span className="flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">
                                <AlertTriangle className="h-3.5 w-3.5" /> Incomplete
                            </span>
                        )}
                    </div>
                    {missingDocs.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                            {missingDocs.map((d) => (
                                <span key={d.doc_type} className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/20 dark:text-amber-300">
                                    {d.label}
                                </span>
                            ))}
                        </div>
                    )}
                </CardShell>
            )}

            {/* Documents table */}
            <CardShell className="overflow-hidden p-0">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Document</th>
                            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Uploaded</th>
                            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {documents && documents.data.length > 0 ? (
                            documents.data.map((doc) => {
                                const isExpanded = expandedDocId === doc.id;
                                return (
                                    <React.Fragment key={doc.id}>
                                        <tr
                                            onClick={() => setExpandedDocId(isExpanded ? null : doc.id)}
                                            className="border-b border-border last:border-0 cursor-pointer transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
                                        >
                                            <td className="px-4 py-3">
                                                <div className="flex items-center gap-2">
                                                    <FileText className="h-4 w-4 text-muted-foreground" />
                                                    <span className="font-medium text-foreground">
                                                        {DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type}
                                                    </span>
                                                </div>
                                            </td>
                                            <td className="px-4 py-3">
                                                <div className="flex flex-col gap-1">
                                                    <span className={cn('inline-block w-fit rounded-full px-2.5 py-0.5 text-xs font-medium', DOC_STATUS_COLORS[doc.status] ?? 'bg-slate-100 text-slate-700')}>
                                                        {doc.status.replace(/_/g, ' ')}
                                                    </span>
                                                    {doc.quality_flags && (() => {
                                                        try {
                                                            const flags: string[] = JSON.parse(doc.quality_flags);
                                                            return flags.length > 0 ? (
                                                                <div className="flex flex-wrap gap-1">
                                                                    {flags.map((flag) => (
                                                                        <span key={flag} className="rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-600 dark:bg-red-900/20 dark:text-red-400">
                                                                            {flag.replace(/_/g, ' ')}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            ) : null;
                                                        } catch { return null; }
                                                    })()}
                                                </div>
                                            </td>
                                            <td className="px-4 py-3 text-muted-foreground">{formatDate(doc.created_at)}</td>
                                            <td className="px-4 py-3">
                                                {doc.status === 'flagged_for_resubmission' || doc.status === 'rejected' ? (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); chatPrefill(`Request resubmission of ${DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type} for application #${appId}.`); }}
                                                        className="text-xs font-medium text-[#1e3a5f] hover:underline"
                                                    >
                                                        Request Resubmission
                                                    </button>
                                                ) : null}
                                            </td>
                                        </tr>
                                        {isExpanded && (
                                            <tr className="border-b border-border bg-slate-50/50 dark:bg-slate-800/30">
                                                <td colSpan={4} className="px-6 py-3">
                                                    <ExtractionDetails appId={appId} documentId={doc.id} />
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                );
                            })
                        ) : (
                            <tr>
                                <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                                    No documents uploaded yet.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </CardShell>

            {/* Upload */}
            <DocumentUpload appId={appId} />
        </div>
    );
}

// -- Conditions tab -----------------------------------------------------------

function ConditionsTab({ appId }: { appId: number }) {
    const { data: conditions, isLoading } = useConditions(appId);

    if (isLoading) {
        return (
            <CardShell>
                <Skeleton className="mb-4 h-6 w-48" />
                <Skeleton className="mb-2 h-16 w-full" />
                <Skeleton className="h-16 w-full" />
            </CardShell>
        );
    }

    const items = conditions?.data ?? [];

    if (items.length === 0) {
        return (
            <CardShell className="flex flex-col items-center gap-3 py-8">
                <CheckCircle2 className="h-8 w-8 text-emerald-500" />
                <p className="text-sm text-muted-foreground">No underwriting conditions.</p>
            </CardShell>
        );
    }

    const isActionable = (status: string | null | undefined) =>
        status === 'open' || status === 'responded' || status === 'escalated';

    return (
        <CardShell className="overflow-hidden p-0">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Condition</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Severity</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Due</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {items.map((cond: Condition) => (
                        <tr key={cond.id} className="border-b border-border last:border-0">
                            <td className="px-4 py-3">
                                <p className="font-medium text-foreground">{cond.description}</p>
                                {cond.response_text && (
                                    <p className="mt-1 text-xs text-muted-foreground italic">Response: {cond.response_text}</p>
                                )}
                            </td>
                            <td className="px-4 py-3">
                                {cond.severity && (
                                    <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', SEVERITY_COLORS[cond.severity] ?? 'bg-slate-100 text-slate-600')}>
                                        {cond.severity.replace(/_/g, ' ')}
                                    </span>
                                )}
                            </td>
                            <td className="px-4 py-3">
                                {cond.status && (
                                    <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', CONDITION_STATUS_COLORS[cond.status] ?? 'bg-slate-100 text-slate-600')}>
                                        {cond.status.replace(/_/g, ' ')}
                                    </span>
                                )}
                            </td>
                            <td className="px-4 py-3 text-muted-foreground">{formatDate(cond.due_date)}</td>
                            <td className="px-4 py-3">
                                {isActionable(cond.status) ? (
                                    <button
                                        onClick={() => chatPrefill(`Respond to condition "${cond.description}" on application #${appId}.`)}
                                        className="text-xs font-medium text-[#1e3a5f] hover:underline"
                                    >
                                        Respond
                                    </button>
                                ) : null}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </CardShell>
    );
}


// -- Main component -----------------------------------------------------------

function LoanDetail() {
    const { applicationId } = Route.useParams();
    const appId = Number(applicationId);
    const [activeTab, setActiveTab] = useState<Tab>('profile');

    const { data: app, isLoading: appLoading } = useApplication(appId);
    const { data: rateLock } = useRateLock(appId);

    if (appLoading) {
        return (
            <div className="mx-auto max-w-[1280px] p-6 md:p-8">
                <Skeleton className="mb-4 h-5 w-48" />
                <CardShell>
                    <Skeleton className="mb-4 h-12 w-full" />
                    <Skeleton className="h-6 w-3/4" />
                </CardShell>
            </div>
        );
    }

    if (!app) {
        return (
            <div className="mx-auto max-w-[1280px] p-6 md:p-8">
                <CardShell className="flex flex-col items-center gap-3 py-12">
                    <AlertTriangle className="h-8 w-8 text-amber-500" />
                    <p className="text-foreground font-medium">Application not found</p>
                    <Link to="/loan-officer" className="text-sm text-[#1e3a5f] hover:underline">
                        Back to Pipeline
                    </Link>
                </CardShell>
            </div>
        );
    }

    const name = borrowerName(app);

    return (
        <div className="mx-auto max-w-[1280px] p-6 md:p-8">
            {/* Breadcrumb */}
            <nav className="mb-4 flex items-center gap-1.5 text-sm text-muted-foreground">
                <Link to="/loan-officer" className="hover:text-foreground transition-colors">Pipeline</Link>
                <ChevronRight className="h-3.5 w-3.5" />
                <span className="text-foreground font-medium">{name}{name !== `Application #${app.id}` ? ` — #${app.id}` : ''}</span>
            </nav>

            {/* Header */}
            <div className="mb-6">
                <DetailHeader app={app} rateLock={rateLock} />
            </div>

            {/* Tabs */}
            <div className="mb-6 flex gap-1 overflow-x-auto border-b border-border">
                {TABS.map((tab) => {
                    const Icon = tab.icon;
                    const isActive = activeTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={cn(
                                'flex items-center gap-1.5 whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
                                isActive
                                    ? 'border-[#1e3a5f] text-[#1e3a5f]'
                                    : 'border-transparent text-muted-foreground hover:text-foreground',
                            )}
                        >
                            <Icon className="h-4 w-4" />
                            {tab.label}
                        </button>
                    );
                })}
            </div>

            {/* Tab content */}
            {activeTab === 'profile' && <ProfileTab app={app} />}
            {activeTab === 'financial' && <FinancialSummaryTab app={app} />}
            {activeTab === 'documents' && <DocumentsTab appId={appId} />}
            {activeTab === 'conditions' && <ConditionsTab appId={appId} />}
        </div>
    );
}
