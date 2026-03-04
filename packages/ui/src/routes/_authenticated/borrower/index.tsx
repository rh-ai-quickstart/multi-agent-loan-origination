// This project was developed with assistance from AI tools.

import { createFileRoute } from '@tanstack/react-router';
import { useState, useRef, useCallback, useEffect } from 'react';
import {
    FileText,
    Upload,
    AlertTriangle,
    Lock,
    Calendar,
    MapPin,
    DollarSign,
    Clock,
    ArrowRight,
    Home,
    Info,
    CheckCircle2,
    Loader2,
    X,
    Award,
} from 'lucide-react';
import { useApplications } from '@/hooks/use-applications';
import { useApplicationStatus } from '@/hooks/use-status';
import { useDocuments, useCompleteness, useUploadDocument } from '@/hooks/use-documents';
import { useConditions } from '@/hooks/use-conditions';
import { useDisclosures } from '@/hooks/use-disclosures';
import { useRateLock } from '@/hooks/use-rate-lock';
import { formatCurrency, formatDate, formatDays, formatPercent } from '@/lib/format';
import { LOAN_TYPE_LABELS, STAGE_ORDER, APPLICATION_STAGE_LABELS, type ApplicationStage } from '@/schemas/enums';
import type { ApplicationResponse } from '@/schemas/applications';
import type { ApplicationStatusResponse } from '@/schemas/status';
import type { DocumentListResponse, CompletenessResponse } from '@/schemas/documents';
import type { ConditionListResponse, Condition } from '@/schemas/conditions';
import type { DisclosureStatusResponse, DisclosureItem } from '@/schemas/disclosures';
import type { RateLockResponse } from '@/schemas/rate-lock';
import { cn } from '@/lib/utils';

export const Route = createFileRoute('/_authenticated/borrower/')({
    component: BorrowerDashboard,
});

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

const STEPPER_STAGES: ApplicationStage[] = [
    'inquiry',
    'prequalification',
    'application',
    'processing',
    'underwriting',
    'conditional_approval',
    'closed',
];

function StageStepper({ currentStage }: { currentStage: ApplicationStage }) {
    const currentIdx = STAGE_ORDER.indexOf(currentStage);

    return (
        <div className="flex items-center justify-between px-2 py-4">
            {STEPPER_STAGES.map((stage, i) => {
                const stageIdx = STAGE_ORDER.indexOf(stage);
                const isCurrent = stage === currentStage;
                const isCompleted = stageIdx < currentIdx;
                const label = APPLICATION_STAGE_LABELS[stage];

                return (
                    <div key={stage} className="flex flex-1 flex-col items-center gap-2">
                        <div className="flex w-full items-center">
                            {i > 0 && (
                                <div
                                    className={cn(
                                        'h-0.5 flex-1',
                                        isCompleted || isCurrent ? 'bg-[#1e3a5f]' : 'bg-slate-200 dark:bg-slate-700',
                                    )}
                                />
                            )}
                            <div
                                className={cn(
                                    'flex shrink-0 items-center justify-center rounded-full transition-all',
                                    isCurrent && 'h-5 w-5 bg-[#1e3a5f] ring-4 ring-[#1e3a5f]/20',
                                    isCompleted && 'h-4 w-4 bg-[#1e3a5f]',
                                    !isCurrent && !isCompleted && 'h-3 w-3 bg-slate-300 dark:bg-slate-600',
                                )}
                            >
                                {isCompleted && <CheckCircle2 className="h-3 w-3 text-white" />}
                            </div>
                            {i < STEPPER_STAGES.length - 1 && (
                                <div
                                    className={cn(
                                        'h-0.5 flex-1',
                                        isCompleted ? 'bg-[#1e3a5f]' : 'bg-slate-200 dark:bg-slate-700',
                                    )}
                                />
                            )}
                        </div>
                        <span
                            className={cn(
                                'text-center text-[10px] font-medium leading-tight',
                                isCurrent ? 'text-[#1e3a5f] dark:text-blue-400' : 'text-muted-foreground',
                            )}
                        >
                            {label}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

function StatusCard({
    application,
    status,
    isLoading,
}: {
    application: ApplicationResponse | undefined;
    status: ApplicationStatusResponse | undefined;
    isLoading: boolean;
}) {
    if (isLoading) {
        return (
            <CardShell>
                <Skeleton className="mb-4 h-6 w-48" />
                <Skeleton className="mb-6 h-16 w-full" />
                <Skeleton className="h-4 w-64" />
            </CardShell>
        );
    }

    if (!application || !status) {
        return (
            <CardShell>
                <p className="text-sm text-muted-foreground">No active application found.</p>
            </CardShell>
        );
    }

    const daysInStage = status.urgency?.days_in_stage ?? null;

    return (
        <CardShell>
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                    <h2 className="text-lg font-semibold text-foreground">
                        Application #{application.id}
                    </h2>
                    <span className="rounded-full bg-[#1e3a5f]/10 px-3 py-0.5 text-xs font-semibold text-[#1e3a5f]">
                        {APPLICATION_STAGE_LABELS[application.stage]}
                    </span>
                </div>
                <p className="text-2xl font-bold text-foreground">
                    {formatCurrency(application.loan_amount)}
                </p>
            </div>

            <StageStepper currentStage={application.stage} />

            <div className="flex flex-wrap gap-6 border-t border-border pt-4 text-sm text-muted-foreground">
                {daysInStage != null && (
                    <div className="flex items-center gap-1.5">
                        <Clock className="h-4 w-4" />
                        <span>{formatDays(daysInStage)} in current stage</span>
                    </div>
                )}
                {status.stage_info.next_step && (
                    <div className="flex items-center gap-1.5">
                        <ArrowRight className="h-4 w-4" />
                        <span>Next: {status.stage_info.next_step}</span>
                    </div>
                )}
            </div>
        </CardShell>
    );
}

const DOC_TYPE_LABELS: Record<string, string> = {
    w2: 'W-2 Form',
    pay_stub: 'Pay Stub',
    tax_return: 'Tax Return',
    bank_statement: 'Bank Statement',
    id: 'Photo ID',
    property_appraisal: 'Property Appraisal',
    insurance: 'Insurance',
    other: 'Other Document',
};

function DocumentsCard({
    documents,
    completeness,
    applicationId,
    isLoading,
}: {
    documents: DocumentListResponse | undefined;
    completeness: CompletenessResponse | undefined;
    applicationId: number | undefined;
    isLoading: boolean;
}) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isDragOver, setIsDragOver] = useState(false);
    const uploadMutation = useUploadDocument(applicationId);

    const handleFileSelect = useCallback(
        (file: File) => {
            uploadMutation.mutate(
                { file, documentType: 'other' },
                { onSuccess: () => { if (fileInputRef.current) fileInputRef.current.value = ''; } },
            );
        },
        [uploadMutation],
    );

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setIsDragOver(false);
            const file = e.dataTransfer.files[0];
            if (file) handleFileSelect(file);
        },
        [handleFileSelect],
    );

    if (isLoading) {
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

    const statusColors: Record<string, string> = {
        uploaded: 'bg-blue-100 text-blue-700',
        processing: 'bg-blue-100 text-blue-700',
        processing_complete: 'bg-blue-100 text-blue-700',
        accepted: 'bg-emerald-100 text-emerald-700',
        pending_review: 'bg-amber-100 text-amber-700',
        flagged_for_resubmission: 'bg-red-100 text-red-700',
        rejected: 'bg-red-100 text-red-700',
        processing_failed: 'bg-red-100 text-red-700',
    };

    return (
        <CardShell>
            <div className="mb-4 flex items-center justify-between">
                <h3 className="text-base font-semibold text-foreground">Documents</h3>
            </div>

            {missingDocs.length > 0 && (
                <div className="mb-4 flex items-start gap-2 rounded-lg bg-amber-50 p-3 dark:bg-amber-900/20">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                    <div className="text-sm text-amber-800 dark:text-amber-200">
                        <p className="font-medium">Missing documents:</p>
                        <p>{missingDocs.map((d) => d.label).join(', ')}</p>
                    </div>
                </div>
            )}

            {documents && documents.data.length > 0 ? (
                <div className="divide-y divide-border">
                    {documents.data.map((doc) => (
                        <div key={doc.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                            <div className="flex items-center gap-3">
                                <FileText className="h-4 w-4 text-muted-foreground" />
                                <div>
                                    <p className="text-sm font-medium text-foreground">
                                        {DOC_TYPE_LABELS[doc.doc_type] ?? doc.doc_type}
                                    </p>
                                    <p className="text-xs text-muted-foreground">{formatDate(doc.created_at)}</p>
                                </div>
                            </div>
                            <span
                                className={cn(
                                    'rounded-full px-2.5 py-0.5 text-xs font-medium',
                                    statusColors[doc.status] ?? 'bg-slate-100 text-slate-700',
                                )}
                            >
                                {doc.status.replace(/_/g, ' ')}
                            </span>
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
            )}

            <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                className="hidden"
                onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                }}
            />

            {uploadMutation.isError && (
                <div className="mt-4 flex items-start gap-2 rounded-lg bg-red-50 p-3 dark:bg-red-900/20">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
                    <p className="text-sm text-red-700 dark:text-red-400">
                        {uploadMutation.error instanceof Error ? uploadMutation.error.message : 'Upload failed'}
                    </p>
                </div>
            )}

            <div
                role="button"
                tabIndex={0}
                onClick={() => !uploadMutation.isPending && fileInputRef.current?.click()}
                onKeyDown={(e) => {
                    if ((e.key === 'Enter' || e.key === ' ') && !uploadMutation.isPending) {
                        e.preventDefault();
                        fileInputRef.current?.click();
                    }
                }}
                onDragOver={(e) => {
                    e.preventDefault();
                    setIsDragOver(true);
                }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDrop}
                className={cn(
                    'mt-4 flex cursor-pointer items-center justify-center rounded-lg border-2 border-dashed py-6 transition-colors',
                    uploadMutation.isPending && 'pointer-events-none opacity-60',
                    isDragOver
                        ? 'border-[#1e3a5f] bg-[#1e3a5f]/5'
                        : 'border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600',
                )}
            >
                <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    {uploadMutation.isPending ? (
                        <Loader2 className="h-6 w-6 animate-spin" />
                    ) : (
                        <Upload className="h-6 w-6" />
                    )}
                    <p className="text-sm">
                        {uploadMutation.isPending ? 'Uploading...' : 'Drop files here or click to upload'}
                    </p>
                </div>
            </div>
        </CardShell>
    );
}

function ConditionsCard({
    conditions,
    isLoading,
}: {
    conditions: ConditionListResponse | undefined;
    isLoading: boolean;
}) {
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
    const openConditions = items.filter((c: Condition) => c.status === 'open' || c.status === 'responded');

    if (openConditions.length === 0) {
        return (
            <CardShell>
                <h3 className="mb-4 text-base font-semibold text-foreground">Underwriting Conditions</h3>
                <div className="flex flex-col items-center gap-2 py-4 text-muted-foreground">
                    <CheckCircle2 className="h-6 w-6 text-emerald-500" />
                    <p className="text-sm">No outstanding conditions</p>
                </div>
            </CardShell>
        );
    }

    const severityColors: Record<string, string> = {
        prior_to_approval: 'text-red-600',
        prior_to_docs: 'text-orange-600',
        prior_to_closing: 'text-amber-600',
        prior_to_funding: 'text-blue-600',
    };

    return (
        <CardShell>
            <h3 className="mb-4 text-base font-semibold text-foreground">Underwriting Conditions</h3>
            <div className="flex flex-col gap-3">
                {openConditions.map((condition: Condition) => {
                    const severity = condition.severity ?? '';
                    const isCritical = severity === 'prior_to_approval';

                    return (
                        <div
                            key={condition.id}
                            className={cn(
                                'rounded-lg border p-4',
                                isCritical
                                    ? 'border-red-200 bg-red-50 dark:border-red-900/50 dark:bg-red-900/10'
                                    : 'border-border',
                            )}
                        >
                            <div className="flex items-start gap-3">
                                {isCritical ? (
                                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red-600" />
                                ) : (
                                    <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                                )}
                                <div className="flex-1">
                                    <p className="text-sm font-medium text-foreground">
                                        {condition.description}
                                    </p>
                                    <div className="mt-1 flex items-center gap-2">
                                        {severity && (
                                            <span
                                                className={cn(
                                                    'text-xs font-medium',
                                                    severityColors[severity] ?? 'text-muted-foreground',
                                                )}
                                            >
                                                {severity.replace(/_/g, ' ')}
                                            </span>
                                        )}
                                        <span className="text-xs text-muted-foreground">
                                            {condition.status}
                                        </span>
                                    </div>
                                </div>
                                <button
                                    onClick={() => {
                                        window.dispatchEvent(
                                            new CustomEvent('chat-prefill', {
                                                detail: {
                                                    message: `I'd like to respond to the condition: ${condition.description}`,
                                                    autoSend: true,
                                                },
                                            }),
                                        );
                                    }}
                                    className={cn(
                                        'shrink-0 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                                        isCritical
                                            ? 'bg-[#1e3a5f] text-white hover:bg-[#152e42]'
                                            : 'border border-border text-foreground hover:bg-slate-50 dark:hover:bg-slate-800',
                                    )}
                                >
                                    Respond
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>
        </CardShell>
    );
}

function DisclosureModal({
    item,
    onClose,
    onAcknowledge,
}: {
    item: DisclosureItem;
    onClose: () => void;
    onAcknowledge: () => void;
}) {
    useEffect(() => {
        function handleKey(e: KeyboardEvent) {
            if (e.key === 'Escape') onClose();
        }
        document.addEventListener('keydown', handleKey);
        return () => document.removeEventListener('keydown', handleKey);
    }, [onClose]);

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
            onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="disclosure-modal-title"
        >
            <div className="relative mx-4 flex max-h-[85vh] w-full max-w-2xl flex-col rounded-xl bg-white shadow-xl dark:bg-slate-900">
                <div className="flex items-center justify-between border-b border-border px-6 py-4">
                    <h2 id="disclosure-modal-title" className="text-lg font-semibold text-foreground">
                        {item.label}
                    </h2>
                    <button
                        onClick={onClose}
                        className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground dark:hover:bg-slate-800"
                        aria-label="Close"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto px-6 py-4">
                    <div className="whitespace-pre-line text-sm leading-relaxed text-foreground">
                        {item.content}
                    </div>
                </div>
                <div className="flex items-center justify-end gap-3 border-t border-border px-6 py-4">
                    <button
                        onClick={onClose}
                        className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-slate-50 dark:hover:bg-slate-800"
                    >
                        Close
                    </button>
                    <button
                        onClick={onAcknowledge}
                        className="rounded-md bg-[#1e3a5f] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#152e42]"
                    >
                        I Acknowledge
                    </button>
                </div>
            </div>
        </div>
    );
}

function DisclosuresCard({
    disclosures,
    isLoading,
}: {
    disclosures: DisclosureStatusResponse | undefined;
    isLoading: boolean;
}) {
    const [reviewingItem, setReviewingItem] = useState<DisclosureItem | null>(null);

    if (isLoading) {
        return (
            <CardShell>
                <Skeleton className="mb-4 h-6 w-40" />
                <Skeleton className="mb-2 h-10 w-full" />
                <Skeleton className="mb-2 h-10 w-full" />
                <Skeleton className="h-10 w-full" />
            </CardShell>
        );
    }

    const items = disclosures?.disclosures ?? [];
    const allAcknowledged = disclosures?.all_acknowledged ?? false;

    if (allAcknowledged) {
        return (
            <CardShell>
                <h3 className="mb-4 text-base font-semibold text-foreground">Disclosures</h3>
                <div className="flex flex-col items-center gap-2 py-4 text-muted-foreground">
                    <CheckCircle2 className="h-6 w-6 text-emerald-500" />
                    <p className="text-sm">All disclosures acknowledged</p>
                </div>
            </CardShell>
        );
    }

    return (
        <>
            {reviewingItem && (
                <DisclosureModal
                    item={reviewingItem}
                    onClose={() => setReviewingItem(null)}
                    onAcknowledge={() => {
                        setReviewingItem(null);
                        window.dispatchEvent(
                            new CustomEvent('chat-prefill', {
                                detail: {
                                    message: `I have reviewed and acknowledge the ${reviewingItem.label}`,
                                    autoSend: true,
                                },
                            }),
                        );
                    }}
                />
            )}
            <CardShell>
                <h3 className="mb-4 text-base font-semibold text-foreground">Disclosures</h3>
                <div className="divide-y divide-border">
                    {items.map((item: DisclosureItem) => (
                        <div key={item.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                            <div className="flex items-center gap-3">
                                <FileText className="h-4 w-4 text-muted-foreground" />
                                <div>
                                    <p className="text-sm font-medium text-foreground">{item.label}</p>
                                    <p className="text-xs text-muted-foreground">{item.summary}</p>
                                </div>
                            </div>
                            {item.acknowledged ? (
                                <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" />
                            ) : (
                                <button
                                    onClick={() => setReviewingItem(item)}
                                    className="shrink-0 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-slate-50 dark:hover:bg-slate-800"
                                >
                                    Review & Acknowledge
                                </button>
                            )}
                        </div>
                    ))}
                </div>
            </CardShell>
        </>
    );
}

function RateLockCard({
    rateLock,
    isLoading,
}: {
    rateLock: RateLockResponse | undefined;
    isLoading: boolean;
}) {
    if (isLoading) {
        return (
            <CardShell>
                <Skeleton className="mb-4 h-6 w-32" />
                <Skeleton className="mb-2 h-12 w-full" />
                <Skeleton className="h-4 w-48" />
            </CardShell>
        );
    }

    if (!rateLock || rateLock.status === 'none') {
        return (
            <CardShell>
                <h3 className="mb-4 text-base font-semibold text-foreground">Rate Lock</h3>
                <div className="flex flex-col items-center gap-2 py-4 text-muted-foreground">
                    <Lock className="h-6 w-6" />
                    <p className="text-sm">No rate lock active</p>
                </div>
            </CardShell>
        );
    }

    const isExpired = rateLock.status === 'expired';
    const daysRemaining = rateLock.days_remaining ?? 0;
    const totalDays = rateLock.lock_date && rateLock.expiration_date
        ? Math.ceil(
            (new Date(rateLock.expiration_date).getTime() - new Date(rateLock.lock_date).getTime()) /
                (1000 * 60 * 60 * 24),
        )
        : 30;
    const progressPct = totalDays > 0 ? Math.max(0, Math.min(100, (daysRemaining / totalDays) * 100)) : 0;

    return (
        <CardShell>
            <div className="mb-4 flex items-center justify-between">
                <h3 className="text-base font-semibold text-foreground">Rate Lock</h3>
                <div
                    className={cn(
                        'flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold',
                        isExpired ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700',
                    )}
                >
                    <Lock className="h-3 w-3" />
                    {isExpired ? 'EXPIRED' : 'RATE LOCKED'}
                </div>
            </div>

            <div className="mb-4 text-center">
                <p className="text-3xl font-bold text-foreground">
                    {rateLock.locked_rate != null ? formatPercent(rateLock.locked_rate / 100) : '--'}
                </p>
                <p className="text-sm text-muted-foreground">Fixed Rate</p>
            </div>

            {rateLock.expiration_date && (
                <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
                    <Calendar className="h-4 w-4" />
                    <span>Expires {formatDate(rateLock.expiration_date)}</span>
                </div>
            )}

            <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{formatDays(daysRemaining)} remaining</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                    <div
                        className={cn(
                            'h-full rounded-full transition-all',
                            daysRemaining <= 7 ? 'bg-amber-500' : 'bg-emerald-500',
                        )}
                        style={{ width: `${progressPct}%` }}
                    />
                </div>
            </div>
        </CardShell>
    );
}

function SummaryCard({
    application,
    isLoading,
}: {
    application: ApplicationResponse | undefined;
    isLoading: boolean;
}) {
    if (isLoading) {
        return (
            <CardShell>
                <Skeleton className="mb-4 h-6 w-40" />
                <Skeleton className="mb-2 h-5 w-full" />
                <Skeleton className="mb-2 h-5 w-full" />
                <Skeleton className="h-5 w-3/4" />
            </CardShell>
        );
    }

    if (!application) return null;

    return (
        <CardShell>
            <h3 className="mb-4 text-base font-semibold text-foreground">Application Summary</h3>
            <div className="flex flex-col gap-4">
                {application.loan_type && (
                    <div className="flex items-start gap-3">
                        <Home className="mt-0.5 h-4 w-4 text-muted-foreground" />
                        <div>
                            <p className="text-xs text-muted-foreground">Loan Type</p>
                            <p className="text-sm font-medium text-foreground">
                                {LOAN_TYPE_LABELS[application.loan_type]}
                            </p>
                        </div>
                    </div>
                )}
                {application.property_address && (
                    <div className="flex items-start gap-3">
                        <MapPin className="mt-0.5 h-4 w-4 text-muted-foreground" />
                        <div>
                            <p className="text-xs text-muted-foreground">Property</p>
                            <p className="text-sm font-medium text-foreground">
                                {application.property_address}
                            </p>
                        </div>
                    </div>
                )}
                <div className="grid grid-cols-2 gap-4 border-t border-border pt-4">
                    <div className="flex items-start gap-3">
                        <DollarSign className="mt-0.5 h-4 w-4 text-muted-foreground" />
                        <div>
                            <p className="text-xs text-muted-foreground">Property Value</p>
                            <p className="text-sm font-medium text-foreground">
                                {formatCurrency(application.property_value)}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <DollarSign className="mt-0.5 h-4 w-4 text-muted-foreground" />
                        <div>
                            <p className="text-xs text-muted-foreground">Loan Amount</p>
                            <p className="text-sm font-medium text-foreground">
                                {formatCurrency(application.loan_amount)}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </CardShell>
    );
}

function PrequalificationCard({
    application,
    isLoading,
}: {
    application: ApplicationResponse | undefined;
    isLoading: boolean;
}) {
    if (isLoading) {
        return (
            <CardShell>
                <Skeleton className="mb-4 h-6 w-48" />
                <Skeleton className="mb-2 h-12 w-full" />
                <Skeleton className="h-4 w-48" />
            </CardShell>
        );
    }

    const prequal = application?.prequalification;
    if (!prequal) return null;

    const isExpired = new Date(prequal.expires_at) < new Date();

    return (
        <CardShell>
            <div className="mb-4 flex items-center justify-between">
                <h3 className="text-base font-semibold text-foreground">Pre-Qualification</h3>
                <div
                    className={cn(
                        'flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold',
                        isExpired ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700',
                    )}
                >
                    <Award className="h-3 w-3" />
                    {isExpired ? 'EXPIRED' : 'PRE-QUALIFIED'}
                </div>
            </div>

            <div className="mb-4 text-center">
                <p className="text-3xl font-bold text-foreground">
                    {formatCurrency(prequal.max_loan_amount)}
                </p>
                <p className="text-sm text-muted-foreground">
                    {prequal.product_name} at {formatPercent(prequal.estimated_rate / 100)}
                </p>
            </div>

            <div className="flex flex-col gap-2 border-t border-border pt-3 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    <span>Issued {formatDate(prequal.issued_at)}</span>
                </div>
                <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    <span>
                        {isExpired
                            ? `Expired ${formatDate(prequal.expires_at)}`
                            : `Expires ${formatDate(prequal.expires_at)}`}
                    </span>
                </div>
            </div>
        </CardShell>
    );
}

function BorrowerDashboard() {
    const applicationsQuery = useApplications();
    const application = applicationsQuery.data?.data?.[0];
    const appId = application?.id;

    const statusQuery = useApplicationStatus(appId);
    const documentsQuery = useDocuments(appId);
    const completenessQuery = useCompleteness(appId);
    const conditionsQuery = useConditions(appId);
    const disclosuresQuery = useDisclosures(appId);
    const rateLockQuery = useRateLock(appId);

    const isInitialLoading = applicationsQuery.isLoading;

    return (
        <div className="mx-auto max-w-[1280px] p-6 md:p-8">
            <div className="flex flex-col gap-6">
                <StatusCard
                    application={application}
                    status={statusQuery.data}
                    isLoading={isInitialLoading || statusQuery.isLoading}
                />

                <div className="grid gap-6 xl:grid-cols-12">
                    <div className="flex flex-col gap-6 xl:col-span-7">
                        <DocumentsCard
                            documents={documentsQuery.data}
                            completeness={completenessQuery.data}
                            applicationId={appId}
                            isLoading={isInitialLoading || documentsQuery.isLoading}
                        />
                        <ConditionsCard
                            conditions={conditionsQuery.data}
                            isLoading={isInitialLoading || conditionsQuery.isLoading}
                        />
                        <DisclosuresCard
                            disclosures={disclosuresQuery.data}
                            isLoading={isInitialLoading || disclosuresQuery.isLoading}
                        />
                    </div>

                    <div className="flex flex-col gap-6 xl:col-span-5">
                        <PrequalificationCard
                            application={application}
                            isLoading={isInitialLoading}
                        />
                        <RateLockCard
                            rateLock={rateLockQuery.data}
                            isLoading={isInitialLoading || rateLockQuery.isLoading}
                        />
                        <SummaryCard
                            application={application}
                            isLoading={isInitialLoading}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
