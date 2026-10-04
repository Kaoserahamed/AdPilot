/**
 * Display formatting helpers.
 *
 * Every function here is total: given the same input it always returns a string,
 * so components never have to guard against a formatter throwing on unexpected
 * API data.
 */

import type { Campaign } from './types';

export const DERIVED_METRIC_LABELS: Record<string, string> = {
  ctr: 'CTR',
  cpc: 'CPC',
  cpa: 'CPA',
  roas: 'ROAS',
};

/** Placeholder shown where a value is genuinely absent, never a zero. */
export const EMPTY_VALUE = '—';

export function formatMetric(metric: string, value: number): string {
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
}

export function formatCurrency(value: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value);
}

export function formatNullable(value: number | null, suffix = ''): string {
  if (value === null || value === undefined) return EMPTY_VALUE;
  return `${value.toLocaleString('en-US', { maximumFractionDigits: 2 })}${suffix}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatSpend(campaign: Campaign): string {
  return formatCurrency(campaign.spend, campaign.currency || 'USD');
}

export function formatUpdated(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}