// This project was developed with assistance from AI tools.

const currencyFmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const currencyPreciseFmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const percentFmt = new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 2 });
const dateFmt = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });

export function formatCurrency(value: number | null | undefined): string {
    if (value == null) return '--';
    return currencyFmt.format(value);
}

export function formatCurrencyPrecise(value: number | null | undefined): string {
    if (value == null) return '--';
    return currencyPreciseFmt.format(value);
}

export function formatPercent(value: number | null | undefined): string {
    if (value == null) return '--';
    return percentFmt.format(value);
}

export function formatDate(value: string | null | undefined): string {
    if (!value) return '--';
    return dateFmt.format(new Date(value));
}

export function formatDateTime(value: string | null | undefined): string {
    if (!value) return '--';
    return dateTimeFmt.format(new Date(value));
}

export function formatDays(value: number | null | undefined): string {
    if (value == null) return '--';
    if (value === 1) return '1 day';
    return `${Math.round(value)} days`;
}
