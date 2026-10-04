import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Publishing from './Publishing';
import type { CampaignStatusResult, PublishResponse, PublishingJob } from './data';
import { errorResponse, makeCampaign, mockRoutes } from './test/helpers';

const READY_CAMPAIGN = makeCampaign({ id: 1, name: 'Summer launch', status: 'READY' });

const PLATFORM = {
  id: 1,
  platform: 'Meta',
  external_campaign_id: 'ext-1',
  status: 'ACTIVE',
  detail: 'Sandbox campaign created',
  updated_at: '2026-03-24T09:41:00Z',
};

function status(overrides: Partial<CampaignStatusResult> = {}): CampaignStatusResult {
  return {
    campaign_id: 1,
    status: 'READY',
    updated_at: '2026-03-24T09:42:00Z',
    platforms: [],
    jobs: [],
    ...overrides,
  };
}

function job(overrides: Partial<PublishingJob> = {}): PublishingJob {
  return {
    id: 5,
    campaign_id: 1,
    status: 'SUCCEEDED',
    attempt: 1,
    error: null,
    created_at: '2026-03-24T09:40:00Z',
    updated_at: '2026-03-24T09:41:00Z',
    ...overrides,
  };
}

function renderPublishing(campaigns = [READY_CAMPAIGN]) {
  const onPublished = vi.fn();
  render(<Publishing campaigns={campaigns} onPublished={onPublished} />);
  return { onPublished, user: userEvent.setup() };
}

describe('Publishing', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('lists every campaign with its current status', async () => {
    mockRoutes({ '/api/v1/campaigns/1/status': status(), '/api/v1/publishing/jobs': [] });
    renderPublishing([READY_CAMPAIGN, makeCampaign({ id: 2, name: 'Course intake', status: 'DRAFT' })]);

    await waitFor(() => expect(screen.getByRole('option', { name: 'Summer launch · READY' })).toBeInTheDocument());
    expect(screen.getByRole('option', { name: 'Course intake · DRAFT' })).toBeInTheDocument();
  });

  it('reports when a campaign has not been submitted to any platform', async () => {
    mockRoutes({ '/api/v1/campaigns/1/status': status(), '/api/v1/publishing/jobs': [] });
    renderPublishing();

    expect(await screen.findByText('Not submitted yet')).toBeInTheDocument();
  });

  it('reports when no publishing jobs exist yet', async () => {
    mockRoutes({ '/api/v1/campaigns/1/status': status(), '/api/v1/publishing/jobs': [] });
    renderPublishing();

    expect(await screen.findByText('No publishing jobs yet')).toBeInTheDocument();
  });

  it('publishes a campaign and surfaces the acceptance message', async () => {
    const publishResponse: PublishResponse = {
      campaign_id: 1,
      status: 'PUBLISHING',
      job: job({ id: 7, status: 'QUEUED' }),
      message: 'Publishing queued for Meta.',
    };
    mockRoutes({
      '/api/v1/publishing/jobs': [job({ id: 7, status: 'QUEUED' })],
      '/api/v1/campaigns/1/status': status({ status: 'PUBLISHING' }),
      'POST /api/v1/campaigns/1/publish': publishResponse,
    });
    const { onPublished, user } = renderPublishing();

    await user.click(screen.getByRole('button', { name: /Publish campaign/ }));

    expect(await screen.findByRole('status')).toHaveTextContent('Publishing queued for Meta.');
    expect(onPublished).toHaveBeenCalled();
  });

  it('shows the publishing error and does not report success on a failed publish', async () => {
    mockRoutes({
      '/api/v1/campaigns/1/status': status(),
      '/api/v1/publishing/jobs': [],
      'POST /api/v1/campaigns/1/publish': errorResponse('A duplicate publish is already queued.', 409),
    });
    const { onPublished, user } = renderPublishing();

    await user.click(screen.getByRole('button', { name: /Publish campaign/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('A duplicate publish is already queued.');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(onPublished).not.toHaveBeenCalled();
  });

it('disables publishing while a job is queued so a duplicate submit is impossible', async () => {
    mockRoutes({
      '/api/v1/campaigns/1/status': status({
        status: 'PUBLISHING',
        jobs: [job({ id: 7, status: 'QUEUED' })],
      }),
      '/api/v1/publishing/jobs': [job({ id: 7, status: 'QUEUED' })],
    });
    renderPublishing();

    await waitFor(() => expect(screen.getByRole('button', { name: /Publish campaign/ })).toBeDisabled());
  });

  it('enables pause only once a platform submission exists', async () => {
    mockRoutes({ '/api/v1/campaigns/1/status': status(), '/api/v1/publishing/jobs': [] });
    renderPublishing();

    expect(await screen.findByRole('button', { name: 'Pause' })).toBeDisabled();
  });

  it('pauses an active campaign', async () => {
    mockRoutes({
      '/api/v1/campaigns/1/status': status({
        status: 'ACTIVE',
        platforms: [PLATFORM],
      }),
      'POST /api/v1/campaigns/1/pause': status({ status: 'PAUSED' }),
      '/api/v1/publishing/jobs': [],
    });
    const { onPublished, user } = renderPublishing();

    await user.click(await screen.findByRole('button', { name: 'Pause' }));

    await waitFor(() => expect(onPublished).toHaveBeenCalled());
  });

  it('surfaces the platform detail and external id for a submitted campaign', async () => {
    mockRoutes({
      '/api/v1/campaigns/1/status': status({ status: 'ACTIVE', platforms: [PLATFORM] }),
      '/api/v1/publishing/jobs': [],
    });
    renderPublishing();

    expect(await screen.findByText('ext-1')).toBeInTheDocument();
    expect(screen.getByText('Sandbox campaign created')).toBeInTheDocument();
  });

  it('offers retry only for a failed job below the three-attempt ceiling', async () => {
    mockRoutes({
      '/api/v1/campaigns/1/status': status(),
      '/api/v1/publishing/jobs': [job({ id: 9, status: 'FAILED', attempt: 1, error: 'Platform timeout' })],
    });
    renderPublishing();

    expect(await screen.findByRole('button', { name: 'Retry' })).toBeInTheDocument();
    expect(screen.getByText('Platform timeout')).toBeInTheDocument();
  });

  it('hides retry once the three-attempt ceiling is reached', async () => {
    mockRoutes({
      '/api/v1/campaigns/1/status': status(),
      '/api/v1/publishing/jobs': [job({ id: 9, status: 'FAILED', attempt: 3, error: 'Platform timeout' })],
    });
    renderPublishing();

    expect(await screen.findByText('Platform timeout')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
  });

  it('retries a failed job and refreshes the campaign list', async () => {
    mockRoutes({
      '/api/v1/campaigns/1/status': status(),
      '/api/v1/publishing/jobs': [job({ id: 9, status: 'FAILED', attempt: 1 })],
      'POST /api/v1/publishing/jobs/9/retry': job({ id: 9, status: 'QUEUED', attempt: 2 }),
    });
    const { onPublished, user } = renderPublishing();

    await user.click(await screen.findByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(onPublished).toHaveBeenCalled());
  });
});