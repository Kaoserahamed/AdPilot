import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import type { AnalyticsOverview, CampaignApi } from './data';
import { errorResponse, mockRoutes } from './test/helpers';

const USER = { id: 1, name: 'Alex Morgan', email: 'alex@northstar.co' };

function campaignApi(overrides: Partial<CampaignApi> = {}): CampaignApi {
  return {
    id: 1,
    name: 'Summer launch',
    product: 'Pro workspace',
    description: 'A workspace for growing teams.',
    objective: 'sales',
    location: 'United States',
    audience: 'Founders',
    budget: 1500,
    currency: 'USD',
    duration_days: 30,
    landing_page: 'https://example.com',
    tone: 'Confident',
    offer: null,
    platforms: ['Meta'],
    status: 'ACTIVE',
    spend: 1248.6,
    created_at: '2026-03-20T09:00:00Z',
    updated_at: '2026-03-24T09:42:00Z',
    ...overrides,
  };
}

const OVERVIEW: AnalyticsOverview = {
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
  platforms: [],
  campaigns: [],
};

/** Route table for a signed-in workspace. */
function workspaceRoutes(campaigns: CampaignApi[] = [campaignApi()], extra: Record<string, unknown> = {}) {
  return {
    '/api/v1/auth/me': USER,
    '/api/v1/campaigns': campaigns,
    '/api/v1/analytics/overview': OVERVIEW,
    ...extra,
  };
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows the sign-in screen when no session exists', async () => {
    mockRoutes({ '/api/v1/auth/me': errorResponse('Authentication required', 401) });
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Welcome back.' })).toBeInTheDocument();
  });

  it('renders the workspace once the session resolves', async () => {
    mockRoutes(workspaceRoutes());
    render(<App />);

    expect(await screen.findByText('Northstar Studio')).toBeInTheDocument();
    expect(screen.getByText('alex@northstar.co')).toBeInTheDocument();
  });

  it('surfaces an unreachable API rather than silently showing the login form', async () => {
    mockRoutes({ '/api/v1/auth/me': errorResponse('Unable to reach the AdPilot API.', 503) });
    render(<App />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach the AdPilot API.');
  });

  it('lists the loaded campaigns in the dashboard table', async () => {
    mockRoutes(workspaceRoutes([campaignApi(), campaignApi({ id: 2, name: 'Course intake', status: 'DRAFT', spend: 0 })]));
    render(<App />);

    const table = await screen.findByRole('table');
    expect(within(table).getByText('Summer launch')).toBeInTheDocument();
    expect(within(table).getByText('Course intake')).toBeInTheDocument();
    expect(within(table).getByText('$1,248.60')).toBeInTheDocument();
  });

  it('prompts the user when there are no campaigns yet', async () => {
    mockRoutes(workspaceRoutes([]));
    render(<App />);

    expect(await screen.findByText('No campaigns yet')).toBeInTheDocument();
  });

  it('shows the campaigns error when the list cannot be loaded', async () => {
    mockRoutes(workspaceRoutes([], { '/api/v1/campaigns': errorResponse('Unable to load campaigns.', 503) }));
    render(<App />);

    expect(await screen.findByText('Unable to load campaigns.')).toBeInTheDocument();
  });

  it('renders overview totals from the analytics endpoint', async () => {
    mockRoutes(workspaceRoutes());
    render(<App />);

    const grid = await screen.findByText('Total spend');
    expect(grid.closest('.metric-card')).toHaveTextContent('Last 7 days');
    expect(screen.getByText('Sandbox mode')).toBeInTheDocument();
  });

  it('switches workspace views from the sidebar', async () => {
    mockRoutes(workspaceRoutes([], { '/api/v1/creatives': [], '/api/v1/platforms': [], '/api/v1/platforms/accounts': [] }));
    render(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Creative library' }));
    expect(await screen.findByRole('heading', { name: 'Creative library' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Connected platforms' }));
    expect(await screen.findByRole('heading', { name: 'Connected platforms' })).toBeInTheDocument();
  });

  it('creates a campaign from the workspace and adds it to the table', async () => {
    const created = campaignApi({ id: 5, name: 'Brand refresh', status: 'DRAFT' });
    mockRoutes(workspaceRoutes([], { 'POST /api/v1/campaigns': created }));
    render(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /New campaign/ }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Campaign name'), 'Brand refresh');
    await user.type(screen.getByLabelText('Product or service'), 'Pro workspace');
    await user.type(screen.getByLabelText('Description'), 'A workspace for growing teams.');
    await user.type(screen.getByLabelText('Target location'), 'United States');
    await user.type(screen.getByLabelText('Target audience'), 'Founders');
    await user.type(screen.getByLabelText('Budget (USD)'), '900');
    await user.type(screen.getByLabelText('Landing page URL'), 'https://example.com/refresh');
    await user.click(screen.getByRole('button', { name: /Create campaign/ }));

    // The modal closes and the new campaign is prepended to the table.
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const table = await screen.findByRole('table');
    expect(within(table).getByText('Brand refresh')).toBeInTheDocument();
    // Creating navigates to the campaign list rather than the overview.
    expect(screen.getByRole('heading', { name: /Your campaigns/ })).toBeInTheDocument();
  });

  it('deletes a campaign from the table row menu', async () => {
    mockRoutes(workspaceRoutes([campaignApi()], { 'DELETE /api/v1/campaigns/1': {} }));
    const fetchMock = vi.mocked(fetch);
    render(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Delete Summer launch' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/campaigns/1', expect.objectContaining({ method: 'DELETE' })));
    await waitFor(() => expect(screen.getByText('No campaigns yet')).toBeInTheDocument());
  });

  it('logs out and returns to the sign-in screen', async () => {
    mockRoutes(workspaceRoutes([], { 'POST /api/v1/auth/logout': {} }));
    render(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Log out' }));

    expect(await screen.findByRole('heading', { name: 'Welcome back.' })).toBeInTheDocument();
  });
});