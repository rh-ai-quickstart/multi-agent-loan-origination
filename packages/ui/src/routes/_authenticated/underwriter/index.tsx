// This project was developed with assistance from AI tools.

import { useState, useMemo } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import {
    Search,
    ClipboardCheck,
    Clock,
    CheckCircle,
    TrendingUp,
    ChevronUp,
    ChevronDown,
    ChevronsUpDown,
    Lock,
} from 'lucide-react';
import { usePipelineApplications } from '@/hooks/use-applications';
import { formatCurrency, formatDays } from '@/lib/format';
import { staffName } from '@/lib/staff-names';
import {
    type ApplicationStage,
    type UrgencyLevel,
} from '@/schemas/enums';
import type { ApplicationResponse } from '@/schemas/applications';
import type { ApplicationsQueryParams } from '@/services/applications';
import { cn } from '@/lib/utils';

export const Route = createFileRoute('/_authenticated/underwriter/')({
    component: UnderwriterQueue,
});

// -- Color maps ---------------------------------------------------------------

const URGENCY_BADGE: Record<string, string> = {
    critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    high: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    medium: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    normal: 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400',
};

const UW_STAGES = new Set<ApplicationStage>(['underwriting', 'conditional_approval']);

// -- Sub-components -----------------------------------------------------------

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

function QueueMetrics({ applications }: { applications: ApplicationResponse[] }) {
    const pending = applications.filter((a) => a.stage === 'underwriting');
    const inProgress = applications.filter((a) => a.stage === 'conditional_approval');
    const today = new Date().toISOString().slice(0, 10);
    const decidedToday = applications.filter((a) =>
        (a.stage === 'closed' || a.stage === 'denied') && a.updated_at?.slice(0, 10) === today,
    );
    const allUw = applications.filter((a) => UW_STAGES.has(a.stage));
    const avgDays =
        allUw.length > 0
            ? Math.round(allUw.reduce((sum, a) => sum + (a.urgency?.days_in_stage ?? 0), 0) / allUw.length * 10) / 10
            : 0;

    const metrics = [
        { label: 'Pending Review', value: pending.length, icon: ClipboardCheck, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-900/30' },
        { label: 'In Progress', value: inProgress.length, icon: Clock, color: 'text-[#1e3a5f]', bg: 'bg-[#1e3a5f]/10' },
        { label: 'Decided Today', value: decidedToday.length, icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-100 dark:bg-emerald-900/30' },
        { label: 'Avg Review Time', value: avgDays, suffix: 'days', icon: TrendingUp, color: 'text-violet-600', bg: 'bg-violet-100 dark:bg-violet-900/30' },
    ];

    return (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {metrics.map((m) => (
                <CardShell key={m.label} className="flex flex-col gap-1 p-5">
                    <span className="text-sm font-medium text-muted-foreground">{m.label}</span>
                    <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-bold text-foreground">{m.value}</span>
                        {m.suffix && <span className="text-sm text-muted-foreground">{m.suffix}</span>}
                    </div>
                </CardShell>
            ))}
        </div>
    );
}

function borrowerName(app: ApplicationResponse): string {
    const primary = app.borrowers?.find((b) => b.is_primary) ?? app.borrowers?.[0];
    if (!primary) return `Application #${app.id}`;
    return `${primary.first_name} ${primary.last_name}`;
}

function rateLockLabel(app: ApplicationResponse): React.ReactNode {
    const factors = app.urgency?.factors ?? [];
    const rateFactor = factors.find((f) => f.toLowerCase().includes('rate lock'));
    if (rateFactor) {
        return (
            <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                <Lock className="h-3 w-3" />
                <span className="truncate max-w-[100px]" title={rateFactor}>{rateFactor}</span>
            </span>
        );
    }
    return <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-400">Floating</span>;
}

// -- Sortable columns ---------------------------------------------------------

type SortKey = 'borrower' | 'loan_amount' | 'assigned_lo' | 'days_in_queue' | 'urgency';
type SortDir = 'asc' | 'desc';

const URGENCY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, normal: 3 };

function compareApps(a: ApplicationResponse, b: ApplicationResponse, key: SortKey, dir: SortDir): number {
    let cmp = 0;
    switch (key) {
        case 'borrower':
            cmp = borrowerName(a).localeCompare(borrowerName(b));
            break;
        case 'loan_amount':
            cmp = (a.loan_amount ?? 0) - (b.loan_amount ?? 0);
            break;
        case 'assigned_lo':
            cmp = staffName(a.assigned_to).localeCompare(staffName(b.assigned_to));
            break;
        case 'days_in_queue':
            cmp = (a.urgency?.days_in_stage ?? 0) - (b.urgency?.days_in_stage ?? 0);
            break;
        case 'urgency':
            cmp = (URGENCY_ORDER[a.urgency?.level ?? 'normal'] ?? 3) - (URGENCY_ORDER[b.urgency?.level ?? 'normal'] ?? 3);
            break;
    }
    return dir === 'asc' ? cmp : -cmp;
}

function SortIcon({ sortKey, activeKey, dir }: { sortKey: SortKey; activeKey: SortKey; dir: SortDir }) {
    if (sortKey !== activeKey) return <ChevronsUpDown className="ml-1 inline h-3.5 w-3.5 opacity-40" />;
    return dir === 'asc'
        ? <ChevronUp className="ml-1 inline h-3.5 w-3.5" />
        : <ChevronDown className="ml-1 inline h-3.5 w-3.5" />;
}

const URGENCY_FILTER: { value: UrgencyLevel | ''; label: string }[] = [
    { value: '', label: 'All Urgency' },
    { value: 'critical', label: 'Critical' },
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'normal', label: 'Normal' },
];

// -- Main component -----------------------------------------------------------

function UnderwriterQueue() {
    const [searchQuery, setSearchQuery] = useState('');
    const [filterUrgency, setFilterUrgency] = useState<UrgencyLevel | ''>('');
    const [sortKey, setSortKey] = useState<SortKey>('urgency');
    const [sortDir, setSortDir] = useState<SortDir>('asc');

    const toggleSort = (key: SortKey) => {
        if (key === sortKey) {
            setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
        } else {
            setSortKey(key);
            setSortDir(key === 'borrower' || key === 'assigned_lo' ? 'asc' : 'desc');
        }
    };

    const params: ApplicationsQueryParams = { limit: 100 };

    const { data, isLoading } = usePipelineApplications(params);
    const applications = useMemo(() => data?.data ?? [], [data]);

    // Filter to underwriting-relevant stages, then apply search + urgency + sort
    const filtered = useMemo(() => {
        let result = applications.filter((a) => UW_STAGES.has(a.stage));
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            result = result.filter((app) => {
                const name = borrowerName(app).toLowerCase();
                const idStr = String(app.id);
                return name.includes(q) || idStr.includes(q);
            });
        }
        if (filterUrgency) {
            result = result.filter((app) => app.urgency?.level === filterUrgency);
        }
        return [...result].sort((a, b) => compareApps(a, b, sortKey, sortDir));
    }, [applications, searchQuery, filterUrgency, sortKey, sortDir]);

    const totalUw = applications.filter((a) => UW_STAGES.has(a.stage)).length;

    return (
        <div className="mx-auto max-w-[1280px] p-6 md:p-8">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-foreground">Underwriting Queue</h1>
                <p className="text-sm text-muted-foreground">Review and decision pending loan applications</p>
            </div>

            {/* Metrics */}
            {isLoading ? (
                <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <CardShell key={i} className="p-5">
                            <Skeleton className="mb-2 h-4 w-24" />
                            <Skeleton className="h-8 w-16" />
                        </CardShell>
                    ))}
                </div>
            ) : (
                <div className="mb-6">
                    <QueueMetrics applications={applications} />
                </div>
            )}

            {/* Filters */}
            <CardShell className="mb-6">
                <div className="flex flex-wrap items-center gap-3">
                    <div className="relative flex-1 min-w-[200px]">
                        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Search by borrower name or ID..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full rounded-lg border border-border bg-transparent py-2 pl-10 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/30"
                        />
                    </div>
                    <select
                        value={filterUrgency}
                        onChange={(e) => setFilterUrgency(e.target.value as UrgencyLevel | '')}
                        className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/30"
                    >
                        {URGENCY_FILTER.map((u) => (
                            <option key={u.value} value={u.value}>{u.label}</option>
                        ))}
                    </select>
                </div>
            </CardShell>

            {/* Table */}
            <CardShell className="overflow-hidden p-0">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                                <th className="px-6 py-3 text-left font-semibold text-muted-foreground cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('borrower')}>
                                    Borrower<SortIcon sortKey="borrower" activeKey={sortKey} dir={sortDir} />
                                </th>
                                <th className="px-6 py-3 text-left font-semibold text-muted-foreground cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('loan_amount')}>
                                    Loan Amount<SortIcon sortKey="loan_amount" activeKey={sortKey} dir={sortDir} />
                                </th>
                                <th className="px-6 py-3 text-left font-semibold text-muted-foreground cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('assigned_lo')}>
                                    Assigned LO<SortIcon sortKey="assigned_lo" activeKey={sortKey} dir={sortDir} />
                                </th>
                                <th className="px-6 py-3 text-left font-semibold text-muted-foreground whitespace-nowrap cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('days_in_queue')}>
                                    Days in Queue<SortIcon sortKey="days_in_queue" activeKey={sortKey} dir={sortDir} />
                                </th>
                                <th className="px-6 py-3 text-left font-semibold text-muted-foreground">Rate Lock</th>
                                <th className="px-6 py-3 text-left font-semibold text-muted-foreground cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('urgency')}>
                                    Urgency<SortIcon sortKey="urgency" activeKey={sortKey} dir={sortDir} />
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                Array.from({ length: 5 }).map((_, i) => (
                                    <tr key={i} className="border-b border-border">
                                        <td className="px-6 py-4" colSpan={6}>
                                            <Skeleton className="h-5 w-full" />
                                        </td>
                                    </tr>
                                ))
                            ) : filtered.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                                        No applications pending review.
                                    </td>
                                </tr>
                            ) : (
                                filtered.map((app) => (
                                    <QueueRow key={app.id} app={app} />
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
                {!isLoading && totalUw > 0 && (
                    <div className="border-t border-border bg-slate-50 px-6 py-3 text-xs text-muted-foreground dark:bg-slate-800/50">
                        Showing {filtered.length} of {totalUw} pending reviews
                    </div>
                )}
            </CardShell>
        </div>
    );
}

function QueueRow({ app }: { app: ApplicationResponse }) {
    const navigate = useNavigate();
    const urgencyLevel = (app.urgency?.level ?? 'normal') as string;
    const name = borrowerName(app);

    const goToDetail = () => navigate({ to: '/underwriter/$applicationId', params: { applicationId: String(app.id) } });

    return (
        <tr
            tabIndex={0}
            role="link"
            onClick={goToDetail}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goToDetail(); } }}
            className="border-b border-border transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#1e3a5f]"
        >
            <td className="px-6 py-4">
                <div>
                    <p className="font-medium text-foreground">{name}</p>
                    <p className="text-xs text-muted-foreground truncate max-w-[220px]" title={app.property_address ?? undefined}>
                        {app.property_address ?? `Application #${app.id}`}
                    </p>
                </div>
            </td>
            <td className="px-6 py-4 font-medium text-foreground">{formatCurrency(app.loan_amount)}</td>
            <td className="px-6 py-4 text-muted-foreground">{staffName(app.assigned_to)}</td>
            <td className="px-6 py-4 whitespace-nowrap text-foreground">
                {(() => {
                    const days = app.urgency?.days_in_stage ?? 0;
                    const dot = days >= 5 ? 'bg-red-500' : days >= 4 ? 'bg-amber-400' : 'bg-emerald-500';
                    const text = days >= 5 ? 'text-red-600' : days >= 4 ? 'text-amber-600' : 'text-foreground';
                    return (
                        <span className={cn('inline-flex items-center gap-1.5 font-medium', text)}>
                            <span className={cn('inline-block h-2 w-2 rounded-full', dot)} />
                            {formatDays(days)}
                        </span>
                    );
                })()}
            </td>
            <td className="px-6 py-4">{rateLockLabel(app)}</td>
            <td className="px-6 py-4">
                <span className={cn('inline-flex items-center rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wide', URGENCY_BADGE[urgencyLevel] ?? URGENCY_BADGE.normal)}>
                    {urgencyLevel}
                </span>
            </td>
        </tr>
    );
}
