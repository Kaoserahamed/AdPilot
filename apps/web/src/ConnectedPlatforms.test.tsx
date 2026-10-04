import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ConnectedPlatforms from './ConnectedPlatforms';
import type { ConnectedAccount, PlatformCapability } from './data';
import { errorResponse, mockRoutes } from './test/helpers';

function capability(platform: string, overrides: Partial<PlatformCapability> = {}): PlatformCapability {
  return {
    platform,
    label: `${platform} Ads`,
    connected: false,
    supports_oauth: true,
    supports_video: false,
    supports_metrics: true,
    supports_pause: true,
    sandbox: true,
    ...overrides,
  };
}

function account(overrides: Partial<ConnectedAccount> = {}): ConnectedAccount {
  return {
    id: 3,
    platform: 'Meta',
    platform_label: 'Meta Ads',
    external_account_id: 'act_12345',
    name: 'Summer launch account',
    currency: 'USD',
    status: 'connected',
    connected_at: '2026-03-24T09:00:00Z',
    sandbox: true,
    ...overrides,
  };
}

const PLATFORMS = [capability('Meta'), capability('Google'), capability('YouTube', { supports_video: true })];
/**
 * Render the platform list.
 *
 * `extra` is merged into the two load routes rather than replacing them, because
 * calling `mockRoutes` twice would re-stub `fetch` and silently drop the
 * per-action routes the test just registered.
 */
function renderPlatforms(accounts: ConnectedAccount[] = [], extra: Record<string, unknown> = {}) {
  mockRoutes({ '/api/v1/platforms': PLATFORMS, '/api/v1/platforms/accounts': accounts, ...extra });
  render(<ConnectedPlatforms />);
  return { user: userEvent.setup() };
}

describe('ConnectedPlatforms', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows a loading state while platforms are fetched', () => {
    mockRoutes({ '/api/v1/platforms': PLATFORMS, '/api/v1/platforms/accounts': [] });
    render(<ConnectedPlatforms />);

    expect(screen.getByText(/Loading connected platforms/)).toBeInTheDocument();
  });

  it('lists every advertising platform as not connected', async () => {
    renderPlatforms();

    expect(await screen.findByText('Meta Ads')).toBeInTheDocument();
    expect(screen.getAllByText('Not connected').length).toBe(3);
  });

  it('marks a platform connected once an account is returned', async () => {
    renderPlatforms([account()]);

    expect(await screen.findByText('Summer launch account')).toBeInTheDocument();
    expect(screen.getByText('act_12345 · USD')).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getAllByText('Not connected').length).toBe(2);
  });

  it('connects a sandbox account for a platform', async () => {
    const { user } = renderPlatforms([], {
      'POST /api/v1/platforms/accounts/connect': account({ platform: 'Google', external_account_id: 'act_999', name: 'Google sandbox' }),
    });
    const fetchMock = vi.mocked(fetch);

    await user.click((await screen.findAllByRole('button', { name: /Connect sandbox account/ }))[0]);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/platforms/accounts/connect',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ platform: 'Meta' }) }),
    );
    expect(await screen.findByText('Google sandbox')).toBeInTheDocument();
  });

  it('disconnects a connected account', async () => {
    const { user } = renderPlatforms([account()], { 'DELETE /api/v1/platforms/accounts/3': {} });
    const fetchMock = vi.mocked(fetch);

    await user.click(await screen.findByRole('button', { name: 'Disconnect' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/platforms/accounts/3', expect.objectContaining({ method: 'DELETE' })));
    await waitFor(() => expect(screen.queryByText('Summer launch account')).not.toBeInTheDocument());
  });

  it('reports a failed connection', async () => {
    const { user } = renderPlatforms([], {
      'POST /api/v1/platforms/accounts/connect': errorResponse('OAuth is not configured for this platform.', 400),
    });

    await user.click((await screen.findAllByRole('button', { name: /Connect sandbox account/ }))[0]);

    expect(await screen.findByRole('alert')).toHaveTextContent('OAuth is not configured for this platform.');
  });

  it('reports a failed disconnect', async () => {
    const { user } = renderPlatforms([account()], {
      'DELETE /api/v1/platforms/accounts/3': errorResponse('Account is still running a campaign.', 409),
    });

    await user.click(await screen.findByRole('button', { name: 'Disconnect' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Account is still running a campaign.');
  });

  it('reports a failure to load the connected accounts', async () => {
    mockRoutes({
      '/api/v1/platforms': PLATFORMS,
      '/api/v1/platforms/accounts': errorResponse('Unable to list accounts.', 503),
    });
    render(<ConnectedPlatforms />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to list accounts.');
  });

  it('marks only the capabilities the adapter actually supports', async () => {
    renderPlatforms();

    await screen.findByText('Meta Ads');
    const cards = document.querySelectorAll('.platform-card');
    expect(cards).toHaveLength(3);
    // YouTube supports video; Meta does not, so both still expose three badges.
    expect(cards[0].querySelectorAll('.capability-list .supported')).toHaveLength(3);
    expect(cards[2].querySelectorAll('.capability-list .supported')).toHaveLength(4);
  });
});