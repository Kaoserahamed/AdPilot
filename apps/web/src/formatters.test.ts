import { describe, expect, it } from 'vitest';
import {
  EMPTY_VALUE,
  formatBytes,
  formatCurrency,
  formatMetric,
  formatNullable,
  formatSpend,
  formatUpdated,
} from './formatters';

describe('formatCurrency', () => {
  it('formats using the requested currency', () => {
    expect(formatCurrency(1248.6, 'USD')).toBe('$1,248.60');
  });

  it('defaults to USD when no currency is given', () => {
    expect(formatCurrency(10)).toBe(formatCurrency(10, 'USD'));
  });

  it('supports a non-dollar currency', () => {
    expect(formatCurrency(1000, 'EUR')).toContain('1,000');
  });

  it('renders zero rather than an empty string', () => {
    expect(formatCurrency(0)).toBe('$0.00');
  });
});

describe('formatMetric', () => {
  it('uses thousands separators', () => {
    expect(formatMetric('impressions', 284000)).toBe('284,000');
  });

  it('caps at two decimal places', () => {
    expect(formatMetric('ctr', 0.018293)).toBe('0.02');
  });

  it('does not label the value, since the column header already does', () => {
    expect(formatMetric('roas', 4.1)).toBe('4.1');
  });
});

describe('formatNullable', () => {
  it('formats a present value', () => {
    expect(formatNullable(12.5)).toBe('12.5');
  });

  it('returns the placeholder for null rather than a misleading zero', () => {
    expect(formatNullable(null)).toBe(EMPTY_VALUE);
  });

  it('appends a suffix to a present value', () => {
    expect(formatNullable(2, '%')).toBe('2%');
  });

  it('does not append a suffix to the placeholder', () => {
    expect(formatNullable(null, '%')).toBe(EMPTY_VALUE);
  });
});

describe('formatBytes', () => {
  it('formats kilobytes below one megabyte', () => {
    expect(formatBytes(2048)).toBe('2 KB');
  });

  it('rounds kilobytes rather than showing decimals', () => {
    expect(formatBytes(1500)).toBe('1 KB');
  });

  it('formats megabytes with one decimal place', () => {
    expect(formatBytes(2_400_000)).toBe('2.3 MB');
  });

  it('formats exactly one megabyte as MB, not 1024 KB', () => {
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB');
  });
});

describe('formatSpend', () => {
  it('formats a campaign spend in its own currency', () => {
    expect(
      formatSpend({
        id: 1,
        name: 'Launch',
        product: 'Product',
        description: 'd',
        objective: 'sales',
        location: 'US',
        audience: 'Founders',
        budget: 1500,
        currency: 'USD',
        durationDays: 30,
        landingPage: 'https://example.com',
        tone: 'Confident',
        platforms: ['Meta'],
        status: 'Active',
        spend: 1248.6,
        createdAt: '2026-03-20T09:00:00Z',
        updatedAt: '2026-03-24T09:42:00Z',
      }),
    ).toBe('$1,248.60');
  });

  it('falls back to USD when the campaign currency is blank', () => {
    expect(formatSpend({ currency: '', spend: 10 } as never)).toBe('$10.00');
  });
});

describe('formatUpdated', () => {
  it('formats an ISO timestamp as a readable date', () => {
    expect(formatUpdated('2026-03-24T09:42:00Z')).toMatch(/Mar\s+24,\s+2026/);
  });

  it('returns the input unchanged when the date cannot be parsed', () => {
    // Returning a mangled "Invalid Date" would be worse than showing the raw value.
    expect(formatUpdated('not-a-date')).toBe('not-a-date');
  });
});