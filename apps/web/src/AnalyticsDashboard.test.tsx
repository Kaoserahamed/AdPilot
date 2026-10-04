import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AnalyticsDashboard from './AnalyticsDashboard';
import type { AnalyticsOverview, PlatformBreakdown } from './data';
import { errorResponse, makeCampaign, mockRoutes } from './test/helpers';

function breakdown(overrides: Partial<PlatformBreakdown> = {}): PlatformBreakdown {
  return {
    platform: 'Meta',
    spend: 1248.6,
    impressions: 284000,
    clicks: 5120,
    conversions: 327,
    ctr: 0.018,
    cpc: 0.24,
    cpa: 3.82,
    roas: 4.1,
    currency: 'USD',
    calculated_fields: ['ctr', 'cpc', 'cpa', 'roas'],
    ...overrides,
  };
}

function overview(overrides: Partial<AnalyticsOverview> = {}): AnalyticsOverview {
  return {
    reporting_period_days: 7,
    active_campaigns: 1,
    draft_campaigns: 0,
    pending_review_campaigns: 0,
    total_spend: 1248.6,
    total_impressions: 284000,
    total_clicks: 5120,
    total_conversions: 327,
    currency: 'USD',
    calculated_fields: ['ctr', 'cpc', 'cpa', 'roas'],
    platforms: [breakdown()],
    campaigns: [
      {
        campaign_id: 1,
        campaign_name: 'Summer launch',
        status: 'ACTIVE',
        reporting_period_days: 7,
        platforms: [breakdown()],
        totals: { spend: 1248.6, impressions: 284000, clicks: 5120, conversions: 327 },
        calculated_fields: ['ctr', 'cpc', 'cpa', 'roas'],
        synced_at: '2026-03-24T09:00:00Z',
      },
    ],
    ...overrides,
  };
}

const CAMPAIGNS = [makeCampaign({ id: 1, name: 'Summer launch', status: 'ACTIVE' })];

/**
 * Render the dashboard and wait for the overview request to settle.
 *
 * The component returns early while loading, so the metric cards and the AI
 * panel do not exist until the overview resolves. Tests that assert on anything
 * below the header must await this before querying.
 */
async function renderDashboard(routes: Record<string, unknown>) {
  mockRoutes(routes);
  const user = userEvent.setup();
  const view = render(<AnalyticsDashboard campaigns={CAMPAIGNS} />);
  await waitFor(() => expect(screen.queryByText(/Loading analytics/)).not.toBeInTheDocument());
  return { user, ...view };
}
const ANSWER = {
  campaign_id: 1,
  question: 'How did this campaign perform?',
  period_start: '2026-03-17T00:00:00Z',
  period_end: '2026-03-24T00:00:00Z',
  summary: 'Spend and conversions both increased over the period.',
  highlights: ['Spend rose 18.4%', 'CPA fell 6.2%'],
  facts: [
    { metric: 'spend', value: 1248.6, currency: 'USD', source: 'Meta', calculated: false, reported_at: '2026-03-24T09:00:00Z' },
  ],
  data_complete: true,
  unavailable: [],
  provider: 'sandbox',
  model: 'deterministic',
};

describe('AnalyticsDashboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows a loading state before the overview resolves', () => {
    // Deliberately synchronous: this asserts the pre-resolution render, so it must
    // not await the settled dashboard.
    mockRoutes({ '/api/v1/analytics/overview': overview() });
    render(<AnalyticsDashboard campaigns={CAMPAIGNS} />);
    expect(screen.getByText(/Loading analytics/)).toBeInTheDocument();
  });

  it('prompts the user to publish when no metrics have been synced', async () => {
    await renderDashboard({ '/api/v1/analytics/overview': overview({ campaigns: [] }) });

    expect(await screen.findByText('No synced metrics yet')).toBeInTheDocument();
  });

  it('renders platform-reported totals', async () => {
    await renderDashboard({ '/api/v1/analytics/overview': overview() });

    // Scoped to the summary cards: the same figures also appear in the breakdown
    // table, so unscoped text queries would match more than one element.
    const cards = document.querySelectorAll('.metric-grid .metric-card');
    expect(cards).toHaveLength(4);
    const labels = Array.from(cards).map((card) => card.querySelector('span')?.textContent);
    expect(labels).toEqual(['Total spend', 'Impressions', 'Clicks', 'Conversions']);

    const values = Array.from(cards).map((card) => card.querySelector('strong')?.textContent);
    expect(values).toEqual(['$1,248.60', '284,000', '5,120', '327']);

    // Every card must attribute its figure to the platform rather than AdPilot.
    for (const card of cards) {
      expect(card.querySelector('small')).toHaveTextContent('Reported by platform');
    }
  });

  it('shows the reporting period in the header badge', async () => {
    await renderDashboard({ '/api/v1/analytics/overview': overview({ reporting_period_days: 14 }) });

    expect(await screen.findByText('Last 14 days')).toBeInTheDocument();
  });

  it('separates AdPilot-derived metrics from platform-reported values', async () => {
    await renderDashboard({ '/api/v1/analytics/overview': overview() });

    await screen.findByText('Platform breakdown');
    // Only ctr/cpc/cpa/roas are derived; spend is reported by the platform.
    expect(screen.getAllByText('AdPilot').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Reported by platform').length).toBeGreaterThan(0);
  });

  it('renders a dash for a derived metric the platform did not report', async () => {
    await renderDashboard({
      '/api/v1/analytics/overview': overview({ platforms: [breakdown({ roas: null })] }),
    });

    await screen.findByText('Platform breakdown');
    // An unreported derived metric renders as an em dash rather than 0 or "null".
    expect(screen.getAllByText(/^\u2014$/).length).toBeGreaterThan(0);
  });

  it('surfaces the API error when the overview cannot be loaded', async () => {
    await renderDashboard({ '/api/v1/analytics/overview': errorResponse('Analytics unavailable.', 503) });

    expect(await screen.findByRole('alert')).toHaveTextContent('Analytics unavailable.');
  });

  it('syncs metrics for the selected campaign', async () => {
    mockRoutes({
      '/api/v1/analytics/overview': overview(),
      'POST /api/v1/analytics/campaigns/1/sync': {},
    });
    // Read the installed mock rather than replacing it, so the route table stays
    // in effect and only the call log is inspected.
    const fetchMock = vi.mocked(fetch);
    render(<AnalyticsDashboard campaigns={CAMPAIGNS} />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Sync metrics' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/analytics/campaigns/1/sync', expect.objectContaining({ method: 'POST' }));
  });

  it('reports a failed metric sync', async () => {
    const { user } = await renderDashboard({
      '/api/v1/analytics/overview': overview(),
      'POST /api/v1/analytics/campaigns/1/sync': errorResponse('No connected account for this platform.', 409),
    });

    await user.click(await screen.findByRole('button', { name: 'Sync metrics' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No connected account for this platform.');
  });

  it('asks the AI assistant and renders a grounded answer with its source facts', async () => {
    const { user } = await renderDashboard({
      '/api/v1/analytics/overview': overview(),
      'POST /api/v1/ai/analyze': ANSWER,
    });

    await user.type(screen.getByLabelText('Question'), 'How did this campaign perform?');
    await user.click(screen.getByRole('button', { name: 'Ask AI' }));

    expect(await screen.findByText('Spend and conversions both increased over the period.')).toBeInTheDocument();
    expect(screen.getByText('Spend rose 18.4%')).toBeInTheDocument();
    // Answers must disclose when the underlying data is incomplete.
    expect(screen.queryByText('Incomplete data')).not.toBeInTheDocument();
  });

  it('flags an answer as incomplete when metrics are missing', async () => {
    const { user } = await renderDashboard({
      '/api/v1/analytics/overview': overview(),
      'POST /api/v1/ai/analyze': { ...ANSWER, data_complete: false, unavailable: ['revenue'] },
    });

    await user.click(screen.getByRole('button', { name: 'Ask AI' }));

    expect(await screen.findByText('Incomplete data')).toBeInTheDocument();
    expect(screen.getByText(/Not reported by any platform: revenue/)).toBeInTheDocument();
  });

  it('reports an error when the assistant cannot answer', async () => {
    const { user } = await renderDashboard({
      '/api/v1/analytics/overview': overview(),
      'POST /api/v1/ai/analyze': errorResponse('No stored metrics to analyse.', 409),
    });

    await user.click(screen.getByRole('button', { name: 'Ask AI' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No stored metrics to analyse.');
  });
});