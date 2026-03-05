// This project was developed with assistance from AI tools.

import { useState, useMemo } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import {
    Search,
    Briefcase,
    Clock,
    AlertTriangle,
    TrendingUp,
    ChevronRight,
    ChevronUp,
    ChevronDown,
    ChevronsUpDown,
    Lock,
} from 'lucide-react';
import { usePipelineApplications } from '@/hooks/use-applications';
import { formatCurrency, formatDate, formatDays } from '@/lib/format';
import {
    APPLICATION_STAGE_LABELS,
    type ApplicationStage,
    type UrgencyLevel,
} from '@/schemas/enums';
import type { ApplicationResponse } from '@/schemas/applications';
import type { ApplicationsQueryParams } from '@/services/applications';
import { cn } from '@/lib/utils';
import { STAGE_BADGE } from '@/lib/labels';

export const Route = createFileRoute('/_authenticated/loan-officer/')({
    component: LoanOfficerPipeline,
});

// -- Color maps ---------------------------------------------------------------

const URGENCY_DOT: Record<string, string> = {
    critical: 'bg-red-500',
    high: 'bg-orange-500',
    medium: 'bg-amber-400',
    normal: 'bg-emerald-500',
};

const ACTIVE_STAGES = new Set<ApplicationStage>([
    'inquiry',
    'prequalification',
    'application',
    'processing',
    'underwriting',
    'conditional_approval',
    'clear_to_close',
]);

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

function PipelineMetrics({ applications }: { applications: ApplicationResponse[] }) {
    const active = applications.filter((a) => ACTIVE_STAGES.has(a.stage));
    const inUnderwriting = applications.filter((a) => a.stage === 'underwriting' || a.stage === 'conditional_approval');
    const critical = applications.filter((a) => a.urgency?.level === 'critical');
    const avgDays =
        active.length > 0
            ? Math.round(active.reduce((sum, a) => sum + (a.urgency?.days_in_stage ?? 0), 0) / active.length)
            : 0;

    const metrics = [
        { label: 'Active Loans', value: active.length, icon: Briefcase, color: 'text-[#1e3a5f]', bg: 'bg-[#1e3a5f]/10' },
        { label: 'In Underwriting', value: inUnderwriting.length, icon: Clock, color: 'text-amber-600', bg: 'bg-amber-100' },
        { label: 'Critical Urgency', value: critical.length, icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-100' },
        { label: 'Avg Days in Stage', value: avgDays, icon: TrendingUp, color: 'text-violet-600', bg: 'bg-violet-100' },
    ];

    return (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {metrics.map((m) => (
                <CardShell key={m.label} className="flex items-center gap-4">
                    <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg', m.bg)}>
                        <m.icon className={cn('h-5 w-5', m.color)} />
                    </div>
                    <div>
                        <p className="text-2xl font-bold text-foreground">{m.value}</p>
                        <p className="text-xs text-muted-foreground">{m.label}</p>
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

function borrowerType(app: ApplicationResponse): string {
    if ((app.borrowers?.length ?? 0) > 1) return 'Co-borrower';
    return 'Individual';
}

function rateLockLabel(app: ApplicationResponse): React.ReactNode {
    const factors = app.urgency?.factors ?? [];
    const rateFactor = factors.find((f) => f.toLowerCase().includes('rate lock'));
    if (rateFactor) {
        return (
            <span className="flex items-center gap-1 text-amber-600">
                <Lock className="h-3 w-3" />
                <span className="truncate max-w-[120px]" title={rateFactor}>{rateFactor}</span>
            </span>
        );
    }
    return <span className="text-muted-foreground">--</span>;
}

function urgencyTooltip(app: ApplicationResponse): string {
    const level = app.urgency?.level ?? 'normal';
    const factors = app.urgency?.factors ?? [];
    if (factors.length === 0) return level;
    return `${level}: ${factors.join('; ')}`;
}

// -- Filter stages for dropdown -----------------------------------------------

const FILTER_STAGES: { value: ApplicationStage | ''; label: string }[] = [
    { value: '', label: 'All Stages' },
    { value: 'inquiry', label: 'Inquiry' },
    { value: 'prequalification', label: 'Pre-Qualification' },
    { value: 'application', label: 'Application' },
    { value: 'processing', label: 'Processing' },
    { value: 'underwriting', label: 'Underwriting' },
    { value: 'conditional_approval', label: 'Decision' },
    { value: 'clear_to_close', label: 'Clear to Close' },
    { value: 'closed', label: 'Closed' },
];

// -- Sortable columns ---------------------------------------------------------

type SortKey = 'borrower' | 'loan_amount' | 'stage' | 'days_in_stage' | 'last_activity';
type SortDir = 'asc' | 'desc';

const STAGE_ORDER: Record<string, number> = {
    inquiry: 0, prequalification: 1, application: 2, processing: 3,
    underwriting: 4, conditional_approval: 5, clear_to_close: 6, closed: 7, denied: 8,
};

function comparePipelineApps(a: ApplicationResponse, b: ApplicationResponse, key: SortKey, dir: SortDir): number {
    let cmp = 0;
    switch (key) {
        case 'borrower':
            cmp = borrowerName(a).localeCompare(borrowerName(b));
            break;
        case 'loan_amount':
            cmp = (a.loan_amount ?? 0) - (b.loan_amount ?? 0);
            break;
        case 'stage':
            cmp = (STAGE_ORDER[a.stage] ?? 99) - (STAGE_ORDER[b.stage] ?? 99);
            break;
        case 'days_in_stage':
            cmp = (a.urgency?.days_in_stage ?? 0) - (b.urgency?.days_in_stage ?? 0);
            break;
        case 'last_activity':
            cmp = (a.updated_at ?? '').localeCompare(b.updated_at ?? '');
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

function LoanOfficerPipeline() {
    // Server-side params
    const [filterStage, setFilterStage] = useState<ApplicationStage | ''>('');
    const [filterStalled, setFilterStalled] = useState(false);

    // Client-side filters + sort
    const [searchQuery, setSearchQuery] = useState('');
    const [filterUrgency, setFilterUrgency] = useState<UrgencyLevel | ''>('');
    const [sortKey, setSortKey] = useState<SortKey>('days_in_stage');
    const [sortDir, setSortDir] = useState<SortDir>('desc');

    const toggleSort = (key: SortKey) => {
        if (key === sortKey) {
            setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
        } else {
            setSortKey(key);
            setSortDir(key === 'borrower' ? 'asc' : 'desc');
        }
    };

    const params: ApplicationsQueryParams = {
        filter_stage: filterStage || undefined,
        filter_stalled: filterStalled || undefined,
        limit: 100,
    };

    const { data, isLoading } = usePipelineApplications(params);
    const applications = useMemo(() => data?.data ?? [], [data]);

    // Client-side filtering (search + urgency) + sort
    const filtered = useMemo(() => {
        let result = applications;
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
        return [...result].sort((a, b) => comparePipelineApps(a, b, sortKey, sortDir));
    }, [applications, searchQuery, filterUrgency, sortKey, sortDir]);

    return (
        <div className="mx-auto max-w-[1280px] p-6 md:p-8">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-foreground">Pipeline</h1>
                <p className="text-sm text-muted-foreground">Manage your assigned loan applications</p>
            </div>

            {/* Metrics */}
            {isLoading ? (
                <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <CardShell key={i}>
                            <Skeleton className="h-10 w-full" />
                        </CardShell>
                    ))}
                </div>
            ) : (
                <div className="mb-6">
                    <PipelineMetrics applications={applications} />
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
                        value={filterStage}
                        onChange={(e) => setFilterStage(e.target.value as ApplicationStage | '')}
                        className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/30"
                    >
                        {FILTER_STAGES.map((s) => (
                            <option key={s.value} value={s.value}>{s.label}</option>
                        ))}
                    </select>
                    <select
                        value={filterUrgency}
                        onChange={(e) => setFilterUrgency(e.target.value as UrgencyLevel | '')}
                        className="rounded-lg border border-border bg-transparent px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-[#1e3a5f]/30"
                    >
                        {URGENCY_FILTER.map((u) => (
                            <option key={u.value} value={u.value}>{u.label}</option>
                        ))}
                    </select>
                    <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                        <input
                            type="checkbox"
                            checked={filterStalled}
                            onChange={(e) => setFilterStalled(e.target.checked)}
                            className="h-4 w-4 rounded border-border text-[#1e3a5f] focus:ring-[#1e3a5f]/30"
                        />
                        Stalled only
                    </label>
                </div>
            </CardShell>

            {/* Table */}
            <CardShell className="overflow-hidden p-0">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-border bg-slate-50 dark:bg-slate-800/50">
                                <th className="px-4 py-3 text-left font-medium text-muted-foreground w-8"></th>
                                <th className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('borrower')}>
                                    Borrower<SortIcon sortKey="borrower" activeKey={sortKey} dir={sortDir} />
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('loan_amount')}>
                                    Loan Amount<SortIcon sortKey="loan_amount" activeKey={sortKey} dir={sortDir} />
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('stage')}>
                                    Stage<SortIcon sortKey="stage" activeKey={sortKey} dir={sortDir} />
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-muted-foreground whitespace-nowrap cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('days_in_stage')}>
                                    Days in Stage<SortIcon sortKey="days_in_stage" activeKey={sortKey} dir={sortDir} />
                                </th>
                                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Rate Lock</th>
                                <th className="px-4 py-3 text-left font-medium text-muted-foreground cursor-pointer select-none hover:text-foreground" onClick={() => toggleSort('last_activity')}>
                                    Last Activity<SortIcon sortKey="last_activity" activeKey={sortKey} dir={sortDir} />
                                </th>
                                <th className="px-4 py-3 w-8"></th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                Array.from({ length: 5 }).map((_, i) => (
                                    <tr key={i} className="border-b border-border">
                                        <td className="px-4 py-4" colSpan={8}>
                                            <Skeleton className="h-5 w-full" />
                                        </td>
                                    </tr>
                                ))
                            ) : filtered.length === 0 ? (
                                <tr>
                                    <td colSpan={8} className="px-4 py-12 text-center text-muted-foreground">
                                        No applications match your filters.
                                    </td>
                                </tr>
                            ) : (
                                filtered.map((app) => (
                                    <PipelineRow key={app.id} app={app} />
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </CardShell>
        </div>
    );
}

function PipelineRow({ app }: { app: ApplicationResponse }) {
    const navigate = useNavigate();
    const urgencyLevel = app.urgency?.level ?? 'normal';
    const name = borrowerName(app);
    const type = borrowerType(app);

    const goToDetail = () => navigate({ to: '/loan-officer/$applicationId', params: { applicationId: String(app.id) } });

    return (
        <tr
            tabIndex={0}
            role="link"
            onClick={goToDetail}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goToDetail(); } }}
            className="border-b border-border transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#1e3a5f]"
        >
            <td className="px-4 py-4">
                <span
                    className={cn('inline-block h-2.5 w-2.5 rounded-full', URGENCY_DOT[urgencyLevel] ?? URGENCY_DOT.normal)}
                    title={urgencyTooltip(app)}
                />
            </td>
            <td className="px-4 py-4">
                <div>
                    <p className="font-medium text-foreground">{name}</p>
                    <p className="text-xs text-muted-foreground">{type} &middot; #{app.id}</p>
                </div>
            </td>
            <td className="px-4 py-4 font-medium text-foreground">{formatCurrency(app.loan_amount)}</td>
            <td className="px-4 py-4">
                <span className={cn('inline-block rounded-full px-2.5 py-0.5 text-xs font-medium', STAGE_BADGE[app.stage] ?? STAGE_BADGE.inquiry)}>
                    {APPLICATION_STAGE_LABELS[app.stage]}
                </span>
            </td>
            <td className="px-4 py-4 text-foreground">{formatDays(app.urgency?.days_in_stage)}</td>
            <td className="px-4 py-4 text-sm">{rateLockLabel(app)}</td>
            <td className="px-4 py-4 text-muted-foreground">{formatDate(app.updated_at)}</td>
            <td className="px-4 py-4">
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
            </td>
        </tr>
    );
}
