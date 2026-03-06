// This project was developed with assistance from AI tools.

import { useState } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import { staffName } from '@/lib/staff-names';
import {
    ChevronRight,
    AlertTriangle,
    CheckCircle2,
    ShieldCheck,
    Scale,
    FileText,
    Gavel,
    Plus,
} from 'lucide-react';
import { useApplication } from '@/hooks/use-applications';
import { useConditions } from '@/hooks/use-conditions';
import { useDecisions } from '@/hooks/use-decisions';
import { useRiskAssessment, useComplianceResult } from '@/hooks/use-underwriting';
import { formatCurrency, formatDate, formatPercent } from '@/lib/format';
import { LOAN_TYPE_LABELS } from '@/schemas/enums';
import type { ApplicationResponse } from '@/schemas/applications';
import type { Condition } from '@/schemas/conditions';
import type { DecisionItem } from '@/schemas/decisions';
import { cn } from '@/lib/utils';

export const Route = createFileRoute('/_authenticated/underwriter/$applicationId')({
    component: UnderwriterDetail,
});

// -- Helpers ------------------------------------------------------------------

const SEVERITY_LABELS: Record<string, string> = {
    prior_to_approval: 'PTA',
    prior_to_docs: 'PTD',
    prior_to_closing: 'PTC',
    prior_to_funding: 'PTF',
};

const SEVERITY_COLORS: Record<string, string> = {
    prior_to_approval: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    prior_to_docs: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    prior_to_closing: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    prior_to_funding: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

const CONDITION_STATUS_COLORS: Record<string, string> = {
    open: 'bg-amber-100 text-amber-700',
    responded: 'bg-blue-100 text-blue-700',
    under_review: 'bg-violet-100 text-violet-700',
    cleared: 'bg-emerald-100 text-emerald-700',
    waived: 'bg-slate-100 text-slate-600',
    escalated: 'bg-red-100 text-red-700',
};

const DECISION_TYPE_LABELS: Record<string, string> = {
    approved: 'Approved',
    conditional_approval: 'Approved w/ Conditions',
    suspended: 'Suspended',
    denied: 'Denied',
};

const DECISION_TYPE_COLORS: Record<string, string> = {
    approved: 'bg-emerald-100 text-emerald-700',
    conditional_approval: 'bg-amber-100 text-amber-700',
    suspended: 'bg-orange-100 text-orange-700',
    denied: 'bg-red-100 text-red-700',
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

// -- Risk Assessment card -----------------------------------------------------

const RATING_COLORS: Record<string, { icon: string; bar: string; barWidth: string }> = {
    Low: { icon: 'text-emerald-500', bar: 'bg-emerald-500', barWidth: 'w-1/3' },
    Medium: { icon: 'text-amber-500', bar: 'bg-amber-500', barWidth: 'w-2/3' },
    High: { icon: 'text-red-500', bar: 'bg-red-500', barWidth: 'w-full' },
};

function ratingStyle(rating: string | null | undefined) {
    return RATING_COLORS[rating ?? ''] ?? { icon: 'text-slate-300', bar: 'bg-slate-300', barWidth: 'w-0' };
}

function RiskAssessmentCard({ appId }: { appId: number }) {
    const { data: assessment, isError } = useRiskAssessment(appId);
    const hasData = assessment && !isError;

    const metrics = hasData
        ? [
              {
                  label: 'Credit',
                  value: assessment.credit_value != null ? String(assessment.credit_value) : '--',
                  detail: assessment.credit_rating ? `${assessment.credit_rating} Risk` : 'No data',
                  rating: assessment.credit_rating,
              },
              {
                  label: 'Capacity (DTI)',
                  value: assessment.dti_value != null ? `${assessment.dti_value}%` : '--',
                  detail: assessment.dti_rating ? `${assessment.dti_rating} Risk` : 'No data',
                  rating: assessment.dti_rating,
              },
              {
                  label: 'Collateral (LTV)',
                  value: assessment.ltv_value != null ? `${assessment.ltv_value}%` : '--',
                  detail: assessment.ltv_rating ? `${assessment.ltv_rating} Risk` : 'No data',
                  rating: assessment.ltv_rating,
              },
          ]
        : [
              { label: 'Credit', value: '--', detail: 'Run assessment to evaluate', rating: null },
              { label: 'Capacity', value: '--', detail: 'Run assessment to evaluate', rating: null },
              { label: 'Collateral', value: '--', detail: 'Run assessment to evaluate', rating: null },
          ];

    return (
        <CardShell>
            <div className="mb-6 flex items-center justify-between">
                <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
                    <Scale className="h-5 w-5 text-muted-foreground" />
                    Risk Assessment
                    {hasData && assessment.overall_risk && (
                        <span className={cn(
                            'ml-2 rounded px-2 py-0.5 text-xs font-medium',
                            assessment.overall_risk === 'Low' && 'bg-emerald-100 text-emerald-700',
                            assessment.overall_risk === 'Medium' && 'bg-amber-100 text-amber-700',
                            assessment.overall_risk === 'High' && 'bg-red-100 text-red-700',
                        )}>
                            {assessment.overall_risk} Risk
                        </span>
                    )}
                </h3>
                <button
                    onClick={() => chatPrefill(`Run a risk assessment on application #${appId}`)}
                    className="flex items-center gap-1.5 rounded-lg bg-[#1e3a5f] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[#152e42]"
                >
                    {hasData ? 'Re-run' : 'Run Assessment'}
                </button>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {metrics.map((m) => {
                    const style = ratingStyle(m.rating);
                    return (
                        <div key={m.label} className="rounded-lg border border-border bg-slate-50 p-4 dark:bg-slate-800/50">
                            <div className="mb-2 flex items-center justify-between">
                                <span className="text-sm font-semibold text-muted-foreground">{m.label}</span>
                                <CheckCircle2 className={cn('h-5 w-5', style.icon)} />
                            </div>
                            <p className="text-2xl font-bold text-foreground">{m.value}</p>
                            <p className="mt-1 text-xs text-muted-foreground">{m.detail}</p>
                            <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                                <div className={cn('h-full rounded-full transition-all', style.bar, style.barWidth)} />
                            </div>
                        </div>
                    );
                })}
            </div>
            {hasData && assessment.warnings && assessment.warnings.length > 0 && (
                <div className="mt-4 space-y-1">
                    {assessment.warnings.map((w, i) => (
                        <p key={i} className="flex items-start gap-2 text-xs text-amber-700 dark:text-amber-400">
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                            {w}
                        </p>
                    ))}
                </div>
            )}
        </CardShell>
    );
}

// -- Compliance Checks card ---------------------------------------------------

const STATUS_BADGE: Record<string, string> = {
    PASS: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    CONDITIONAL_PASS: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    WARNING: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    FAIL: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

function ComplianceChecksCard({ appId }: { appId: number }) {
    const { data: result, isError } = useComplianceResult(appId);
    const hasData = result && !isError;

    const checks = [
        { key: 'ecoa' as const, name: 'ECOA (Fair Lending)', icon: Scale },
        { key: 'atr_qm' as const, name: 'ATR/QM (Ability to Repay)', icon: ShieldCheck },
        { key: 'trid' as const, name: 'TRID (Disclosure Timing)', icon: FileText },
    ];

    return (
        <CardShell>
            <div className="mb-4 flex items-center justify-between">
                <h4 className="text-sm font-bold uppercase tracking-wider text-foreground">
                    Compliance Checks
                    {hasData && result.overall_status && (
                        <span className={cn('ml-2 rounded px-2 py-0.5 text-xs font-medium', STATUS_BADGE[result.overall_status] ?? 'bg-slate-100 text-slate-600')}>
                            {result.overall_status.replace(/_/g, ' ')}
                        </span>
                    )}
                </h4>
                <button
                    onClick={() => chatPrefill(`Run compliance checks on application #${appId}`)}
                    className="flex items-center gap-1.5 rounded-lg bg-[#1e3a5f] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[#152e42]"
                >
                    {hasData ? 'Re-run' : 'Run Checks'}
                </button>
            </div>
            <div className="space-y-2">
                {checks.map((check) => {
                    const Icon = check.icon;
                    const status = hasData ? (result[`${check.key}_status`] as string | null) : null;
                    const rationale = hasData ? (result[`${check.key}_rationale`] as string | null) : null;
                    return (
                        <div key={check.key} className="rounded border border-border bg-white p-3 dark:bg-slate-800">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="rounded bg-slate-100 p-1 dark:bg-slate-700">
                                        <Icon className="h-4 w-4 text-slate-500" />
                                    </div>
                                    <span className="text-sm font-medium text-foreground">{check.name}</span>
                                </div>
                                {status ? (
                                    <span className={cn('rounded px-2 py-0.5 text-xs font-medium', STATUS_BADGE[status] ?? 'bg-slate-100 text-slate-600')}>
                                        {status.replace(/_/g, ' ')}
                                    </span>
                                ) : (
                                    <span className="text-xs text-muted-foreground">Pending</span>
                                )}
                            </div>
                            {rationale && (
                                <p className="mt-1.5 pl-10 text-xs text-muted-foreground">{rationale}</p>
                            )}
                        </div>
                    );
                })}
            </div>
        </CardShell>
    );
}

// -- Conditions card ----------------------------------------------------------

function ConditionsCard({ appId }: { appId: number }) {
    const { data: conditions, isLoading } = useConditions(appId);
    const items = conditions?.data ?? [];
    const openCount = items.filter((c) => c.status === 'open' || c.status === 'responded' || c.status === 'escalated').length;

    if (isLoading) {
        return (
            <CardShell>
                <Skeleton className="mb-4 h-5 w-40" />
                <Skeleton className="mb-2 h-12 w-full" />
                <Skeleton className="h-12 w-full" />
            </CardShell>
        );
    }

    return (
        <CardShell>
            <div className="mb-4 flex items-center justify-between">
                <h4 className="text-sm font-bold uppercase tracking-wider text-foreground">
                    Conditions {openCount > 0 && `(${openCount} Open)`}
                </h4>
                <button
                    onClick={() => chatPrefill(`Issue a new condition for application #${appId}`)}
                    className="flex items-center gap-1.5 rounded-lg bg-[#1e3a5f] px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-[#152e42]"
                >
                    <Plus className="h-3.5 w-3.5" />
                    Issue New Condition
                </button>
            </div>
            {items.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-6 text-muted-foreground">
                    <CheckCircle2 className="h-6 w-6 text-emerald-500" />
                    <p className="text-sm">No conditions issued.</p>
                </div>
            ) : (
                <ul className="space-y-2">
                    {items.map((cond: Condition) => (
                        <li key={cond.id} className="flex gap-3 rounded border border-border bg-slate-50 p-3 text-sm dark:bg-slate-800/50">
                            <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                            <div className="flex-1 min-w-0">
                                <p className="font-medium text-foreground">{cond.description}</p>
                                {cond.response_text && (
                                    <p className="mt-0.5 text-xs text-muted-foreground italic">Response: {cond.response_text}</p>
                                )}
                            </div>
                            <div className="flex shrink-0 items-start gap-2">
                                {cond.status && (
                                    <span className={cn('rounded px-2 py-0.5 text-xs font-medium', CONDITION_STATUS_COLORS[cond.status] ?? 'bg-slate-100 text-slate-600')}>
                                        {cond.status.replace(/_/g, ' ')}
                                    </span>
                                )}
                                {cond.severity && (
                                    <span className={cn('rounded px-2 py-0.5 text-xs font-semibold', SEVERITY_COLORS[cond.severity] ?? 'bg-slate-100 text-slate-600')}>
                                        {SEVERITY_LABELS[cond.severity] ?? cond.severity}
                                    </span>
                                )}
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </CardShell>
    );
}

// -- Preliminary Recommendation banner ----------------------------------------

function RecommendationBanner({ appId }: { appId: number }) {
    const { data: assessment, isError } = useRiskAssessment(appId);
    const hasData = assessment && !isError;

    if (!hasData) {
        return (
            <div className="rounded-r-lg border-l-4 border-amber-500 bg-amber-50 p-4 dark:bg-amber-900/10">
                <p className="mb-1 text-xs font-bold uppercase tracking-wider text-amber-700 dark:text-amber-500">
                    Preliminary Recommendation
                </p>
                <p className="text-sm text-amber-800/80 dark:text-amber-300/80">
                    Click &quot;Run Assessment&quot; above to generate risk metrics and a recommendation.
                </p>
            </div>
        );
    }

    const rec = assessment.recommendation;
    const hasRec = rec != null;

    // Color by recommendation outcome, fallback to risk level
    const isApprove = rec?.toLowerCase().includes('approve');
    const isDeny = rec?.toLowerCase().includes('deny');
    const isSuspend = rec?.toLowerCase().includes('suspend');

    let borderColor: string, bgColor: string, titleColor: string, textColor: string;
    if (hasRec) {
        if (isDeny) {
            borderColor = 'border-red-500';
            bgColor = 'bg-red-50 dark:bg-red-900/10';
            titleColor = 'text-red-700 dark:text-red-500';
            textColor = 'text-red-800/80 dark:text-red-300/80';
        } else if (isSuspend) {
            borderColor = 'border-orange-500';
            bgColor = 'bg-orange-50 dark:bg-orange-900/10';
            titleColor = 'text-orange-700 dark:text-orange-500';
            textColor = 'text-orange-800/80 dark:text-orange-300/80';
        } else if (isApprove) {
            borderColor = 'border-emerald-500';
            bgColor = 'bg-emerald-50 dark:bg-emerald-900/10';
            titleColor = 'text-emerald-700 dark:text-emerald-500';
            textColor = 'text-emerald-800/80 dark:text-emerald-300/80';
        } else {
            borderColor = 'border-amber-500';
            bgColor = 'bg-amber-50 dark:bg-amber-900/10';
            titleColor = 'text-amber-700 dark:text-amber-500';
            textColor = 'text-amber-800/80 dark:text-amber-300/80';
        }
    } else {
        // No recommendation yet -- show risk level colors
        const risk = assessment.overall_risk;
        borderColor = risk === 'Low' ? 'border-emerald-500' : risk === 'Medium' ? 'border-amber-500' : 'border-red-500';
        bgColor = risk === 'Low' ? 'bg-emerald-50 dark:bg-emerald-900/10' : risk === 'Medium' ? 'bg-amber-50 dark:bg-amber-900/10' : 'bg-red-50 dark:bg-red-900/10';
        titleColor = risk === 'Low' ? 'text-emerald-700 dark:text-emerald-500' : risk === 'Medium' ? 'text-amber-700 dark:text-amber-500' : 'text-red-700 dark:text-red-500';
        textColor = risk === 'Low' ? 'text-emerald-800/80 dark:text-emerald-300/80' : risk === 'Medium' ? 'text-amber-800/80 dark:text-amber-300/80' : 'text-red-800/80 dark:text-red-300/80';
    }

    return (
        <div className={cn('rounded-r-lg border-l-4 p-4', borderColor, bgColor)}>
            <p className={cn('mb-1 text-xs font-bold uppercase tracking-wider', titleColor)}>
                {hasRec ? `Recommendation: ${rec}` : `Risk Assessment: ${assessment.overall_risk} Risk`}
            </p>
            {hasRec && assessment.recommendation_rationale && assessment.recommendation_rationale.length > 0 && (
                <ul className={cn('mt-1 space-y-0.5 text-sm', textColor)}>
                    {assessment.recommendation_rationale.map((r, i) => (
                        <li key={i}>- {r}</li>
                    ))}
                </ul>
            )}
            {hasRec && assessment.recommendation_conditions && assessment.recommendation_conditions.length > 0 && (
                <div className={cn('mt-2 text-sm', textColor)}>
                    <span className="font-medium">Conditions: </span>
                    <ul className="mt-0.5 space-y-0.5">
                        {assessment.recommendation_conditions.map((c, i) => (
                            <li key={i}>{i + 1}. {c}</li>
                        ))}
                    </ul>
                </div>
            )}
            {!hasRec && (
                <p className={cn('text-sm', textColor)}>
                    Re-run the assessment to generate a recommendation.
                </p>
            )}
        </div>
    );
}

// -- Decision panel -----------------------------------------------------------

function DecisionPanel({ appId }: { appId: number }) {
    const [decision, setDecision] = useState<string>('');
    const [rationale, setRationale] = useState('');

    const options = [
        { value: 'approved', label: 'Approve' },
        { value: 'conditional_approval', label: 'Approve w/ Conditions' },
        { value: 'suspended', label: 'Suspend' },
        { value: 'denied', label: 'Deny' },
    ];

    const canSubmit = decision !== '' && rationale.trim().length > 0;

    const handleSubmit = () => {
        if (!canSubmit) return;
        const label = options.find((o) => o.value === decision)?.label ?? decision;
        const msg = `Record decision: ${label} for application #${appId}. Rationale: ${rationale.trim()}`;
        chatPrefill(msg);
    };

    return (
        <CardShell className="shadow-lg">
            <h3 className="mb-4 text-lg font-bold text-foreground flex items-center gap-2">
                <Gavel className="h-5 w-5 text-muted-foreground" />
                Make Decision
            </h3>
            <div className="mb-6 space-y-3">
                {options.map((opt) => {
                    const isSelected = decision === opt.value;
                    return (
                        <label
                            key={opt.value}
                            className={cn(
                                'flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors',
                                isSelected
                                    ? 'border-[#1e3a5f]/50 bg-[#1e3a5f]/5 ring-1 ring-[#1e3a5f]'
                                    : 'border-border hover:bg-slate-50 dark:hover:bg-slate-800',
                            )}
                        >
                            <input
                                type="radio"
                                name="decision"
                                value={opt.value}
                                checked={isSelected}
                                onChange={() => setDecision(opt.value)}
                                className="h-4 w-4 text-[#1e3a5f] focus:ring-[#1e3a5f]"
                            />
                            <span className={cn('text-sm font-medium', isSelected ? 'font-bold text-[#1e3a5f]' : 'text-foreground')}>
                                {opt.label}
                            </span>
                        </label>
                    );
                })}
            </div>
            <div className="mb-4">
                <label className="mb-2 block text-sm font-medium text-foreground">Rationale / Notes</label>
                <textarea
                    value={rationale}
                    onChange={(e) => setRationale(e.target.value)}
                    placeholder="Enter decision rationale..."
                    rows={4}
                    className="w-full resize-none rounded-lg border border-border bg-transparent p-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/30"
                />
            </div>
            <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#1e3a5f] py-3 font-bold text-white shadow-md transition-colors hover:bg-[#152e42] disabled:opacity-40"
            >
                <Gavel className="h-4 w-4" />
                Record Decision
            </button>
        </CardShell>
    );
}

// -- Application Summary mini-card --------------------------------------------

function AppSummaryCard({ app }: { app: ApplicationResponse }) {
    const loanType = app.loan_type ? LOAN_TYPE_LABELS[app.loan_type] : '--';
    const ltv = app.loan_amount && app.property_value
        ? formatPercent(app.loan_amount / app.property_value)
        : '--';

    return (
        <CardShell>
            <h4 className="mb-3 text-sm font-bold text-foreground flex items-center gap-2">
                <FileText className="h-4 w-4 text-muted-foreground" />
                Application Summary
            </h4>
            <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                    <span className="text-muted-foreground">Loan Type</span>
                    <span className="font-medium text-foreground">{loanType}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-muted-foreground">Loan Amount</span>
                    <span className="font-medium text-foreground">{formatCurrency(app.loan_amount)}</span>
                </div>
                <div className="flex justify-between">
                    <span className="text-muted-foreground">Property Value</span>
                    <span className="font-medium text-foreground">{formatCurrency(app.property_value)}</span>
                </div>
                <div className="flex justify-between border-t border-border pt-2">
                    <span className="text-muted-foreground">LTV</span>
                    <span className="font-bold text-foreground">{ltv}</span>
                </div>
            </div>
        </CardShell>
    );
}

// -- Compliance KB search card ------------------------------------------------

const KB_TOPICS = [
    { label: 'ECOA / Fair Lending', query: 'Search compliance KB for ECOA fair lending requirements and prohibited bases' },
    { label: 'ATR/QM Rules', query: 'Search compliance KB for ability to repay and qualified mortgage safe harbor requirements' },
    { label: 'TRID Timing', query: 'Search compliance KB for TRID Loan Estimate and Closing Disclosure timing requirements' },
    { label: 'PMI / LTV Guidelines', query: 'Search compliance KB for PMI requirements and LTV thresholds' },
    { label: 'FHA Requirements', query: 'Search compliance KB for FHA loan eligibility and requirements' },
    { label: 'Fannie Mae Guidelines', query: 'Search compliance KB for Fannie Mae conventional loan guidelines' },
] as const;

function ComplianceKBCard() {
    return (
        <CardShell>
            <h4 className="mb-3 text-sm font-bold text-foreground">Compliance Knowledge Base</h4>
            <p className="mb-3 text-xs text-muted-foreground">
                Ask the assistant about regulations, guidelines, or internal policies.
            </p>
            <div className="grid grid-cols-2 gap-2">
                {KB_TOPICS.map((topic) => (
                    <button
                        key={topic.label}
                        onClick={() => chatPrefill(topic.query)}
                        className="rounded-full border border-border px-3 py-1 text-xs text-foreground transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                        {topic.label}
                    </button>
                ))}
            </div>
        </CardShell>
    );
}

// -- Past decisions card ------------------------------------------------------

function PastDecisions({ appId }: { appId: number }) {
    const { data, isLoading } = useDecisions(appId);
    const decisions = data?.data ?? [];

    if (isLoading) return null;
    if (decisions.length === 0) return null;

    return (
        <CardShell>
            <h4 className="mb-3 text-sm font-bold text-foreground">Past Decisions</h4>
            <div className="space-y-2">
                {decisions.map((d: DecisionItem) => (
                    <div key={d.id} className="rounded border border-border p-3 text-sm">
                        <div className="flex items-center justify-between">
                            <span className={cn('rounded px-2 py-0.5 text-xs font-medium', DECISION_TYPE_COLORS[d.decision_type] ?? 'bg-slate-100 text-slate-600')}>
                                {DECISION_TYPE_LABELS[d.decision_type] ?? d.decision_type}
                            </span>
                            <span className="text-xs text-muted-foreground">{formatDate(d.created_at)}</span>
                        </div>
                        {d.rationale && (
                            <p className="mt-1.5 text-xs text-muted-foreground">{d.rationale}</p>
                        )}
                        {d.decided_by && (
                            <p className="mt-1 text-xs text-muted-foreground italic">by {staffName(d.decided_by)}</p>
                        )}
                    </div>
                ))}
            </div>
        </CardShell>
    );
}

// -- Main component -----------------------------------------------------------

function UnderwriterDetail() {
    const { applicationId } = Route.useParams();
    const appId = Number(applicationId);

    const { data: app, isLoading: appLoading } = useApplication(appId);

    if (appLoading) {
        return (
            <div className="mx-auto max-w-[1280px] p-6 md:p-8">
                <Skeleton className="mb-4 h-5 w-48" />
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
                    <div className="lg:col-span-8 space-y-6">
                        <Skeleton className="h-64 w-full" />
                        <Skeleton className="h-40 w-full" />
                    </div>
                    <div className="lg:col-span-4 space-y-6">
                        <Skeleton className="h-80 w-full" />
                        <Skeleton className="h-40 w-full" />
                    </div>
                </div>
            </div>
        );
    }

    if (!app) {
        return (
            <div className="mx-auto max-w-[1280px] p-6 md:p-8">
                <CardShell className="flex flex-col items-center gap-3 py-12">
                    <AlertTriangle className="h-8 w-8 text-amber-500" />
                    <p className="font-medium text-foreground">Application not found</p>
                    <Link to="/underwriter" className="text-sm text-[#1e3a5f] hover:underline">
                        Back to Queue
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
                <Link to="/underwriter" className="transition-colors hover:text-foreground">Queue</Link>
                <ChevronRight className="h-3.5 w-3.5" />
                <span className="font-medium text-foreground">{name} — #{app.id}</span>
            </nav>

            {/* Two-column layout */}
            <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
                {/* Left column */}
                <div className="flex flex-col gap-6 lg:col-span-8">
                    <RiskAssessmentCard appId={appId} />
                    <ComplianceChecksCard appId={appId} />
                    <ConditionsCard appId={appId} />
                    <RecommendationBanner appId={appId} />
                </div>

                {/* Right column (sticky) */}
                <div className="flex flex-col gap-6 lg:col-span-4 lg:sticky lg:top-[80px]">
                    <DecisionPanel appId={appId} />
                    <AppSummaryCard app={app} />
                    <ComplianceKBCard />
                    <PastDecisions appId={appId} />
                </div>
            </div>
        </div>
    );
}
