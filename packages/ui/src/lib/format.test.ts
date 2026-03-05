// This project was developed with assistance from AI tools.

import { describe, it, expect } from 'vitest';
import {
    formatCurrency,
    formatCurrencyPrecise,
    formatPercent,
    formatDate,
    formatDateTime,
    formatDays,
} from './format';

describe('formatCurrency', () => {
    it('should format a positive number as USD without decimals', () => {
        expect(formatCurrency(350000)).toBe('$350,000');
    });

    it('should return -- for null', () => {
        expect(formatCurrency(null)).toBe('--');
    });

    it('should return -- for undefined', () => {
        expect(formatCurrency(undefined)).toBe('--');
    });

    it('should format zero', () => {
        expect(formatCurrency(0)).toBe('$0');
    });
});

describe('formatCurrencyPrecise', () => {
    it('should format with two decimal places', () => {
        expect(formatCurrencyPrecise(1234.5)).toBe('$1,234.50');
    });

    it('should return -- for null', () => {
        expect(formatCurrencyPrecise(null)).toBe('--');
    });
});

describe('formatPercent', () => {
    it('should format a decimal ratio as a percentage', () => {
        // 0.065 -> "6.5%"
        const result = formatPercent(0.065);
        expect(result).toMatch(/6\.5%/);
    });

    it('should return -- for null', () => {
        expect(formatPercent(null)).toBe('--');
    });

    it('should return -- for undefined', () => {
        expect(formatPercent(undefined)).toBe('--');
    });

    it('should format zero', () => {
        const result = formatPercent(0);
        expect(result).toMatch(/0/);
    });
});

describe('formatDate', () => {
    it('should format an ISO date string', () => {
        const result = formatDate('2025-06-15T12:00:00Z');
        expect(result).toContain('Jun');
        expect(result).toContain('2025');
    });

    it('should return -- for null', () => {
        expect(formatDate(null)).toBe('--');
    });

    it('should return -- for empty string', () => {
        expect(formatDate('')).toBe('--');
    });
});

describe('formatDateTime', () => {
    it('should include time in the output', () => {
        const result = formatDateTime('2025-06-15T14:30:00Z');
        expect(result).toContain('Jun');
        expect(result).toContain('2025');
    });

    it('should return -- for null', () => {
        expect(formatDateTime(null)).toBe('--');
    });
});

describe('formatDays', () => {
    it('should return singular form for 1 day', () => {
        expect(formatDays(1)).toBe('1 day');
    });

    it('should return plural form for multiple days', () => {
        expect(formatDays(5)).toBe('5 days');
    });

    it('should round fractional days', () => {
        expect(formatDays(2.7)).toBe('3 days');
    });

    it('should return -- for null', () => {
        expect(formatDays(null)).toBe('--');
    });

    it('should return -- for undefined', () => {
        expect(formatDays(undefined)).toBe('--');
    });

    it('should handle zero days', () => {
        expect(formatDays(0)).toBe('0 days');
    });
});
