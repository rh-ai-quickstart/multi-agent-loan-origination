// This project was developed with assistance from AI tools.

import { useState } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';
import {
    Activity,
    TrendingDown,
    Users,
    Shield,
    ChevronDown,
    ChevronUp,
    Star,
} from 'lucide-react';
import { usePipelineSummary, useDenialTrends, useLOPerformance } from '@/hooks/use-analytics';
import { useAuditEvents } from '@/hooks/use-audit';
import type { PipelineSummary } from '@/schemas/analytics';
import type { DenialTrends } from '@/schemas/analytics';
import type { LOPerformanceSummary } from '@/schemas/analytics';
import type { AuditSearchResponse, AuditEventItem } from '@/schemas/audit';
import { cn } from '@/lib/utils';
import { staffName } from '@/lib/staff-names';
import { COMPANY_NAME } from '@/lib/company';

export const Route = createFileRoute('/_authenticated/ceo/')({
    component: CeoDashboard,
});

// -- Helpers ------------------------------------------------------------------

const DEFAULT_DAYS = 180;

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

function CardHeader({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
    return (
        <div className="mb-4 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#1e3a5f]/10">
                <Icon className="h-4 w-4 text-[#1e3a5f]" />
            </div>
            <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        </div>
    );
}

function initials(name: string): string {
    return name
        .split(/\s+/)
        .map((w) => w[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
}

// -- Cards --------------------------------------------------------------------

function PipelineOverviewCard({ data }: { data: PipelineSummary }) {
    const maxCount = Math.max(...data.by_stage.map((s) => s.count), 1);

    const STAGE_LABELS: Record<string, string> = {
        prospect: 'Prospect',
        pre_qualification: 'Pre-Qualification',
        application: 'Application',
        underwriting: 'Underwriting',
        conditional_approval: 'Conditional Approval',
        clear_to_close: 'Clear to Close',
        closed: 'Closed',
        denied: 'Denied',
    };

    return (
        <CardShell>
            <CardHeader icon={Activity} title="Pipeline Overview" />
            <div className="space-y-3">
                {data.by_stage.map((stage) => (
                    <div key={stage.stage}>
                        <div className="mb-1 flex items-center justify-between text-sm">
                            <span className="text-muted-foreground">{STAGE_LABELS[stage.stage] ?? stage.stage}</span>
                            <span className="font-medium text-foreground">{stage.count}</span>
                        </div>
                        <div className="h-2.5 w-full rounded-full bg-slate-100 dark:bg-slate-800">
                            <div
                                className="h-2.5 rounded-full bg-[#1e3a5f]"
                                style={{ width: `${(stage.count / maxCount) * 100}%` }}
                            />
                        </div>
                    </div>
                ))}
            </div>
            <div className="mt-6 grid grid-cols-3 gap-4 border-t border-border pt-4">
                <div>
                    <p className="text-xs text-muted-foreground">Pull-Through Rate</p>
                    <p className="text-lg font-bold text-foreground">{data.pull_through_rate.toFixed(1)}%</p>
                </div>
                <div>
                    <p className="text-xs text-muted-foreground">Avg Days to Close</p>
                    <p className="text-lg font-bold text-foreground">
                        {data.avg_days_to_close != null ? data.avg_days_to_close.toFixed(1) : '--'}
                    </p>
                </div>
                <div>
                    <p className="text-xs text-muted-foreground">Active Applications</p>
                    <p className="text-lg font-bold text-foreground">{data.total_applications}</p>
                </div>
            </div>
        </CardShell>
    );
}

function PipelineOverviewSkeleton() {
    return (
        <CardShell>
            <CardHeader icon={Activity} title="Pipeline Overview" />
            <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i}>
                        <div className="mb-1 flex justify-between">
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-4 w-8" />
                        </div>
                        <Skeleton className="h-2.5 w-full" />
                    </div>
                ))}
            </div>
            <div className="mt-6 grid grid-cols-3 gap-4 border-t border-border pt-4">
                {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i}>
                        <Skeleton className="mb-1 h-3 w-20" />
                        <Skeleton className="h-6 w-12" />
                    </div>
                ))}
            </div>
        </CardShell>
    );
}

function DenialAnalysisCard({ data }: { data: DenialTrends }) {
    const maxRate = Math.max(...data.trend.map((t) => t.denial_rate), 1);
    const maxReasonPct = Math.max(...data.top_reasons.map((r) => r.percentage), 1);

    return (
        <CardShell>
            <CardHeader icon={TrendingDown} title="Denial Analysis" />

            {/* Avg rate badge */}
            <div className="mb-4 flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Overall Denial Rate</span>
                <span className={cn(
                    'rounded-full px-2.5 py-0.5 text-sm font-bold',
                    data.overall_denial_rate > 15
                        ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        : data.overall_denial_rate > 10
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                            : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
                )}>
                    {data.overall_denial_rate.toFixed(1)}%
                </span>
            </div>

            {/* Bar chart (pure CSS) */}
            {data.trend.length > 0 && (
                <div className="mb-4">
                    <div className="flex items-end gap-1" style={{ height: 100 }}>
                        {data.trend.map((point) => (
                            <div key={point.period} className="group relative flex h-full flex-1 items-end">
                                <div
                                    className="w-full rounded-t bg-[#1e3a5f] transition-colors hover:bg-[#152e42]"
                                    style={{ height: `${(point.denial_rate / maxRate) * 100}%`, minHeight: 4 }}
                                    title={`${point.period}: ${point.denial_rate.toFixed(1)}%`}
                                />
                            </div>
                        ))}
                    </div>
                    <div className="mt-1 flex gap-1">
                        {data.trend.map((point) => (
                            <div key={point.period} className="flex-1 text-center text-[10px] text-muted-foreground truncate">
                                {point.period}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Top reasons */}
            <div>
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">Top Denial Reasons</h3>
                <div className="space-y-2">
                    {data.top_reasons.slice(0, 3).map((reason) => (
                        <div key={reason.reason}>
                            <div className="mb-0.5 flex items-center justify-between text-sm">
                                <span className="truncate text-foreground">{reason.reason}</span>
                                <span className="ml-2 shrink-0 text-muted-foreground">{reason.percentage.toFixed(1)}%</span>
                            </div>
                            <div className="h-1.5 w-full rounded-full bg-slate-100 dark:bg-slate-800">
                                <div
                                    className="h-1.5 rounded-full bg-red-400 dark:bg-red-500"
                                    style={{ width: `${(reason.percentage / maxReasonPct) * 100}%` }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </CardShell>
    );
}

function DenialAnalysisSkeleton() {
    return (
        <CardShell>
            <CardHeader icon={TrendingDown} title="Denial Analysis" />
            <div className="mb-4 flex items-center gap-2">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-6 w-14 rounded-full" />
            </div>
            <div className="mb-4 flex items-end gap-1" style={{ height: 100 }}>
                {[40, 65, 30, 80, 55, 45].map((h, i) => (
                    <div key={i} className="flex-1" style={{ height: `${h}%` }}>
                        <Skeleton className="h-full w-full" />
                    </div>
                ))}
            </div>
            <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i}>
                        <Skeleton className="mb-1 h-4 w-3/4" />
                        <Skeleton className="h-1.5 w-full" />
                    </div>
                ))}
            </div>
        </CardShell>
    );
}

function LOPerformanceCard({ data }: { data: LOPerformanceSummary }) {
    const lowestDenialRate = Math.min(...data.loan_officers.map((lo) => lo.denial_rate));

    return (
        <CardShell className="overflow-hidden p-0">
            <div className="p-6 pb-0">
                <CardHeader icon={Users} title="Loan Officer Performance" />
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                            <th className="px-6 py-3 text-left font-semibold text-muted-foreground">Name</th>
                            <th className="px-6 py-3 text-right font-semibold text-muted-foreground">Active</th>
                            <th className="px-6 py-3 text-right font-semibold text-muted-foreground">Closed</th>
                            <th className="px-6 py-3 text-right font-semibold text-muted-foreground">Denial Rate</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.loan_officers.length === 0 ? (
                            <tr>
                                <td colSpan={4} className="px-6 py-8 text-center text-muted-foreground">
                                    No loan officer data available.
                                </td>
                            </tr>
                        ) : (
                            data.loan_officers.map((lo) => {
                                const isTopPerformer = lo.denial_rate === lowestDenialRate && data.loan_officers.length > 1;
                                const rateColor = lo.denial_rate > 15
                                    ? 'text-red-600 dark:text-red-400'
                                    : lo.denial_rate > 10
                                        ? 'text-amber-600 dark:text-amber-400'
                                        : 'text-emerald-600 dark:text-emerald-400';
                                const name = lo.lo_name ?? staffName(lo.lo_id);

                                return (
                                    <tr
                                        key={lo.lo_id}
                                        className={cn(
                                            'border-b border-border',
                                            isTopPerformer && 'bg-emerald-50/50 dark:bg-emerald-900/10',
                                        )}
                                    >
                                        <td className="px-6 py-3">
                                            <div className="flex items-center gap-3">
                                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#1e3a5f] text-xs font-bold text-white">
                                                    {initials(name)}
                                                </div>
                                                <span className="font-medium text-foreground">
                                                    {name}
                                                    {isTopPerformer && (
                                                        <Star className="ml-1 inline h-3.5 w-3.5 text-amber-500" />
                                                    )}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-3 text-right text-foreground">{lo.active_count}</td>
                                        <td className="px-6 py-3 text-right text-foreground">{lo.closed_count}</td>
                                        <td className={cn('px-6 py-3 text-right font-bold', rateColor)}>
                                            {lo.denial_rate.toFixed(1)}%
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>
        </CardShell>
    );
}

function LOPerformanceSkeleton() {
    return (
        <CardShell className="overflow-hidden p-0">
            <div className="p-6 pb-0">
                <CardHeader icon={Users} title="Loan Officer Performance" />
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                            <th className="px-6 py-3 text-left font-semibold text-muted-foreground">Name</th>
                            <th className="px-6 py-3 text-right font-semibold text-muted-foreground">Active</th>
                            <th className="px-6 py-3 text-right font-semibold text-muted-foreground">Closed</th>
                            <th className="px-6 py-3 text-right font-semibold text-muted-foreground">Denial Rate</th>
                        </tr>
                    </thead>
                    <tbody>
                        {Array.from({ length: 3 }).map((_, i) => (
                            <tr key={i} className="border-b border-border">
                                <td className="px-6 py-3"><Skeleton className="h-5 w-32" /></td>
                                <td className="px-6 py-3"><Skeleton className="ml-auto h-5 w-8" /></td>
                                <td className="px-6 py-3"><Skeleton className="ml-auto h-5 w-8" /></td>
                                <td className="px-6 py-3"><Skeleton className="ml-auto h-5 w-12" /></td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </CardShell>
    );
}

const EVENT_TYPE_BADGE: Record<string, string> = {
    application_created: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    application_updated: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
    stage_transition: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
    document_uploaded: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
    decision_made: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    compliance_check: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    risk_assessment: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    condition_added: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400',
    condition_cleared: 'bg-lime-100 text-lime-700 dark:bg-lime-900/30 dark:text-lime-400',
};

function eventDescription(event: AuditEventItem): string {
    const data = event.event_data;
    if (!data) return event.event_type.replace(/_/g, ' ');

    if (typeof data.description === 'string') return data.description;
    if (typeof data.message === 'string') return data.message;
    if (typeof data.detail === 'string') return data.detail;

    // Build a description from known fields
    if (event.event_type === 'stage_transition' && data.from_stage && data.to_stage) {
        return `${String(data.from_stage)} -> ${String(data.to_stage)}`;
    }
    if (event.event_type === 'decision_made' && data.decision) {
        return `Decision: ${String(data.decision)}`;
    }

    return event.event_type.replace(/_/g, ' ');
}

function formatTimestamp(ts: string): string {
    const d = new Date(ts);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
        ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function AuditEventsCard({ data }: { data: AuditSearchResponse }) {
    const [isExpanded, setIsExpanded] = useState(true);

    return (
        <CardShell className="overflow-hidden p-0">
            <div className="flex items-center justify-between p-6 pb-0">
                <CardHeader icon={Shield} title="Recent Audit Events" />
                <button
                    onClick={() => setIsExpanded((v) => !v)}
                    className="rounded-md p-1 text-muted-foreground hover:bg-slate-100 hover:text-foreground dark:hover:bg-slate-800"
                >
                    {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
            </div>
            {isExpanded && (
                <>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                                    <th className="px-6 py-3 text-left font-semibold text-muted-foreground">Timestamp</th>
                                    <th className="px-6 py-3 text-left font-semibold text-muted-foreground">Event Type</th>
                                    <th className="px-6 py-3 text-left font-semibold text-muted-foreground">User</th>
                                    <th className="px-6 py-3 text-left font-semibold text-muted-foreground">Description</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.events.length === 0 ? (
                                    <tr>
                                        <td colSpan={4} className="px-6 py-8 text-center text-muted-foreground">
                                            No audit events found.
                                        </td>
                                    </tr>
                                ) : (
                                    data.events.map((event) => {
                                        const badgeClass = EVENT_TYPE_BADGE[event.event_type] ??
                                            'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-400';
                                        return (
                                            <tr key={event.id} className="border-b border-border">
                                                <td className="whitespace-nowrap px-6 py-3 text-muted-foreground">
                                                    {formatTimestamp(event.timestamp)}
                                                </td>
                                                <td className="px-6 py-3">
                                                    <span className={cn('inline-flex items-center rounded px-2 py-0.5 text-xs font-medium', badgeClass)}>
                                                        {event.event_type.replace(/_/g, ' ')}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-3 text-muted-foreground">
                                                    {event.user_role ?? event.user_id ?? '--'}
                                                </td>
                                                <td className="max-w-[300px] truncate px-6 py-3 text-foreground" title={eventDescription(event)}>
                                                    {eventDescription(event)}
                                                </td>
                                            </tr>
                                        );
                                    })
                                )}
                            </tbody>
                        </table>
                    </div>
                    <div className="border-t border-border bg-slate-50 px-6 py-3 text-xs text-muted-foreground dark:bg-slate-800/50">
                        <Link to="/ceo/audit" className="text-[#1e3a5f] hover:underline dark:text-sky-400">
                            View Full Audit Trail
                        </Link>
                    </div>
                </>
            )}
        </CardShell>
    );
}

function AuditEventsSkeleton() {
    return (
        <CardShell className="overflow-hidden p-0">
            <div className="p-6 pb-0">
                <CardHeader icon={Shield} title="Recent Audit Events" />
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                            <th className="px-6 py-3 text-left font-semibold text-muted-foreground">Timestamp</th>
                            <th className="px-6 py-3 text-left font-semibold text-muted-foreground">Event Type</th>
                            <th className="px-6 py-3 text-left font-semibold text-muted-foreground">User</th>
                            <th className="px-6 py-3 text-left font-semibold text-muted-foreground">Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        {Array.from({ length: 5 }).map((_, i) => (
                            <tr key={i} className="border-b border-border">
                                <td className="px-6 py-3"><Skeleton className="h-4 w-28" /></td>
                                <td className="px-6 py-3"><Skeleton className="h-5 w-24 rounded" /></td>
                                <td className="px-6 py-3"><Skeleton className="h-4 w-16" /></td>
                                <td className="px-6 py-3"><Skeleton className="h-4 w-48" /></td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </CardShell>
    );
}

// -- Main component -----------------------------------------------------------

function CeoDashboard() {

    const pipeline = usePipelineSummary(DEFAULT_DAYS);
    const denials = useDenialTrends(DEFAULT_DAYS);
    const loPerformance = useLOPerformance(DEFAULT_DAYS);
    const auditEvents = useAuditEvents(5);

    return (
        <div className="mx-auto max-w-[1280px] p-6 md:p-8">
            {/* Header */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-foreground">Executive Dashboard</h1>
                <p className="text-sm text-muted-foreground">{COMPANY_NAME} -- Portfolio Health & Operations</p>
            </div>

            {/* 2-col grid */}
            <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
                {pipeline.isLoading ? <PipelineOverviewSkeleton /> : pipeline.data ? <PipelineOverviewCard data={pipeline.data} /> : null}
                {denials.isLoading ? <DenialAnalysisSkeleton /> : denials.data ? <DenialAnalysisCard data={denials.data} /> : null}
            </div>

            {/* LO Performance - full width */}
            <div className="mb-6">
                {loPerformance.isLoading ? <LOPerformanceSkeleton /> : loPerformance.data ? <LOPerformanceCard data={loPerformance.data} /> : null}
            </div>

            {/* Audit events - full width */}
            {auditEvents.isLoading ? <AuditEventsSkeleton /> : auditEvents.data ? <AuditEventsCard data={auditEvents.data} /> : null}

        </div>
    );
}
