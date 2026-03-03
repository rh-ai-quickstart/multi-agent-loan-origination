// This project was developed with assistance from AI tools.

import { useState, type FormEvent } from 'react';
import { DollarSign, Percent } from 'lucide-react';
import { useCalculator } from '@/hooks/use-calculator';
import { useChatContext } from '@/contexts/chat-context';
import { Label } from '@/components/atoms/label/label';
import { formatCurrency } from '@/lib/format';
import type { AffordabilityRequest } from '@/schemas/affordability';

interface FormState {
    gross_annual_income: string;
    monthly_debts: string;
    down_payment: string;
    interest_rate: string;
}

const INITIAL_FORM: FormState = {
    gross_annual_income: '120000',
    monthly_debts: '500',
    down_payment: '60000',
    interest_rate: '6.5',
};

function NumberInputField({
    id,
    label,
    value,
    onChange,
    placeholder,
    icon: Icon,
    required,
}: {
    id: string;
    label: string;
    value: string;
    onChange: (val: string) => void;
    placeholder?: string;
    icon: typeof DollarSign;
    required?: boolean;
}) {
    return (
        <div className="flex flex-col gap-1.5">
            <Label htmlFor={id} className="text-sm font-medium text-foreground">
                {label}
                {required && <span className="ml-1 text-destructive" aria-hidden="true">*</span>}
            </Label>
            <div className="relative">
                <span
                    className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-muted-foreground"
                    aria-hidden="true"
                >
                    <Icon className="h-4 w-4" />
                </span>
                <input
                    id={id}
                    type="number"
                    min={0}
                    step="any"
                    required={required}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={placeholder}
                    className="flex h-11 w-full rounded-lg border border-input bg-slate-50 py-2 pl-9 pr-3 text-sm ring-offset-background transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-slate-800"
                    aria-label={label}
                />
            </div>
        </div>
    );
}

export function AffordabilityForm() {
    const [form, setForm] = useState<FormState>(INITIAL_FORM);
    const { mutate, data: results, isPending, isError } = useCalculator();
    const { openChat } = useChatContext();

    function setField(field: keyof FormState) {
        return (val: string) => setForm((prev) => ({ ...prev, [field]: val }));
    }

    function handleSubmit(e: FormEvent<HTMLFormElement>) {
        e.preventDefault();

        const req: AffordabilityRequest = {
            gross_annual_income: parseFloat(form.gross_annual_income),
            monthly_debts: parseFloat(form.monthly_debts),
            down_payment: parseFloat(form.down_payment),
        };

        if (form.interest_rate) {
            req.interest_rate = parseFloat(form.interest_rate);
        }

        mutate(req);
    }

    const hasResults = !!results;

    return (
        <section id="calculator" className="w-full py-16 lg:py-24">
            <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
                {/* Section header */}
                <div className="mb-12 flex flex-col items-center gap-3 text-center">
                    <span className="text-xs font-semibold uppercase tracking-widest text-[#cc0000]">
                        Affordability Calculator
                    </span>
                    <h2 className="font-display text-3xl font-bold text-foreground sm:text-4xl">
                        How much home can you afford?
                    </h2>
                    <p className="max-w-2xl text-base text-muted-foreground">
                        Enter your financial details to get a personalized estimate of your
                        home buying power.
                    </p>
                </div>

                {/* Calculator card */}
                <div className="overflow-hidden rounded-2xl border border-border shadow-lg">
                    <div className="flex flex-col lg:flex-row">
                        {/* Left: form */}
                        <div className="flex-1 p-6 lg:w-3/5 lg:p-10">
                            <form onSubmit={handleSubmit} aria-label="Affordability calculator form">
                                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                                    <NumberInputField
                                        id="gross_annual_income"
                                        label="Annual Income"
                                        value={form.gross_annual_income}
                                        onChange={setField('gross_annual_income')}
                                        placeholder="120,000"
                                        icon={DollarSign}
                                        required
                                    />
                                    <NumberInputField
                                        id="monthly_debts"
                                        label="Monthly Debts"
                                        value={form.monthly_debts}
                                        onChange={setField('monthly_debts')}
                                        placeholder="500"
                                        icon={DollarSign}
                                        required
                                    />
                                    <NumberInputField
                                        id="down_payment"
                                        label="Down Payment"
                                        value={form.down_payment}
                                        onChange={setField('down_payment')}
                                        placeholder="60,000"
                                        icon={DollarSign}
                                        required
                                    />
                                    <NumberInputField
                                        id="interest_rate"
                                        label="Interest Rate (optional)"
                                        value={form.interest_rate}
                                        onChange={setField('interest_rate')}
                                        placeholder="6.5"
                                        icon={Percent}
                                    />
                                </div>

                                <button
                                    type="submit"
                                    disabled={isPending}
                                    className="mt-6 flex h-11 w-full items-center justify-center rounded-lg bg-[#1e3a5f] px-6 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#2b5a8f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1e3a5f] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                                    aria-busy={isPending}
                                >
                                    {isPending ? 'Calculating...' : 'Calculate'}
                                </button>

                                {isError && (
                                    <p role="alert" className="mt-3 text-center text-sm text-destructive">
                                        Unable to calculate. Please check your inputs and try again.
                                    </p>
                                )}

                                <button
                                    type="button"
                                    onClick={() => openChat("I'd like to estimate my monthly mortgage payment for a specific home price. Please ask me for the home price, down payment, and any other details you need.")}
                                    className="mt-4 w-full cursor-pointer text-center text-sm text-[#1e3a5f] underline decoration-[#1e3a5f]/30 underline-offset-2 transition-colors hover:text-[#2b5a8f] hover:decoration-[#2b5a8f]/50 dark:text-blue-300 dark:decoration-blue-300/30 dark:hover:text-blue-200"
                                >
                                    Have a specific home in mind? Ask our assistant
                                </button>
                            </form>
                        </div>

                        {/* Right: results */}
                        <div className="flex flex-col justify-center gap-6 bg-slate-50 p-6 dark:bg-slate-800 lg:w-2/5 lg:p-10">
                            <div className="flex flex-col gap-4">
                                {hasResults && results.dti_warning && results.estimated_monthly_payment <= 0 ? (
                                    <div className="rounded-xl border border-amber-300 bg-amber-50 p-6 dark:border-amber-700 dark:bg-amber-950/30">
                                        <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">
                                            Debt-to-Income Too High
                                        </p>
                                        <p className="mt-2 text-sm leading-relaxed text-amber-700 dark:text-amber-400">
                                            {results.dti_warning}
                                        </p>
                                        <p className="mt-3 text-xs text-amber-600 dark:text-amber-500">
                                            Try reducing monthly debts or increasing annual income to see your estimated budget.
                                        </p>
                                    </div>
                                ) : (
                                    <>
                                        {/* Budget result */}
                                        <div className="rounded-xl border border-border bg-white p-5 dark:bg-card">
                                            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                                Estimated Home Budget
                                            </p>
                                            {isPending ? (
                                                <p className="font-display text-3xl font-bold text-muted-foreground animate-pulse">
                                                    Calculating...
                                                </p>
                                            ) : hasResults ? (
                                                <p className="font-display text-3xl font-bold text-[#1e3a5f] dark:text-blue-300">
                                                    {formatCurrency(results.estimated_purchase_price)}
                                                </p>
                                            ) : (
                                                <p className="font-display text-3xl font-bold text-muted-foreground">
                                                    --
                                                </p>
                                            )}
                                        </div>

                                        {/* Monthly payment result */}
                                        <div className="rounded-xl border border-border bg-white p-5 dark:bg-card">
                                            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                                Est. Monthly Payment
                                            </p>
                                            {isPending ? (
                                                <p className="font-display text-3xl font-bold text-muted-foreground animate-pulse">
                                                    Calculating...
                                                </p>
                                            ) : hasResults ? (
                                                <p className="font-display text-3xl font-bold text-emerald-600 dark:text-emerald-400">
                                                    {formatCurrency(results.estimated_monthly_payment)}
                                                    <span className="ml-1 text-base font-normal text-muted-foreground">
                                                        /mo
                                                    </span>
                                                </p>
                                            ) : (
                                                <p className="font-display text-3xl font-bold text-muted-foreground">
                                                    --
                                                </p>
                                            )}
                                        </div>

                                        {/* DTI warning (non-blocking) */}
                                        {hasResults && results.dti_warning && (
                                            <p role="alert" className="text-xs text-amber-600 dark:text-amber-400">
                                                {results.dti_warning}
                                            </p>
                                        )}
                                    </>
                                )}
                            </div>

                            <p className="text-xs leading-5 text-muted-foreground">
                                Estimates are for illustrative purposes only and do not constitute
                                a loan commitment. Actual rates and terms may vary. Summit Cap
                                Financial is a fictional company created for demonstration purposes.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
