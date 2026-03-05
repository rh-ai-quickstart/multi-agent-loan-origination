// This project was developed with assistance from AI tools.
import { describe, expect, it } from 'vitest';

import { STAFF_NAMES, staffName } from './staff-names';

describe('staffName', () => {
    it('should return the display name for a known CEO UUID', () => {
        expect(staffName('d1a2b3c4-e5f6-7890-abcd-ef1234567801')).toBe('Sarah Mitchell');
    });

    it('should return the display name for a known underwriter UUID', () => {
        expect(staffName('d1a2b3c4-e5f6-7890-abcd-ef1234567803')).toBe('Maria Chen');
    });

    it('should return the display name for a known loan officer UUID', () => {
        expect(staffName('d1a2b3c4-e5f6-7890-abcd-ef1234567802')).toBe('James Torres');
    });

    it('should return first 8 chars of UUID for unknown users', () => {
        expect(staffName('abcdef01-2345-6789-abcd-ef0123456789')).toBe('abcdef01');
    });

    it('should return "--" for null', () => {
        expect(staffName(null)).toBe('--');
    });

    it('should return "--" for undefined', () => {
        expect(staffName(undefined)).toBe('--');
    });

    it('should return "--" for empty string', () => {
        expect(staffName('')).toBe('--');
    });
});

describe('STAFF_NAMES', () => {
    it('should contain all expected staff entries', () => {
        expect(Object.keys(STAFF_NAMES)).toHaveLength(7);
    });

    it('should have UUIDs as keys', () => {
        for (const key of Object.keys(STAFF_NAMES)) {
            expect(key).toMatch(/^[0-9a-f-]{36}$/);
        }
    });
});
