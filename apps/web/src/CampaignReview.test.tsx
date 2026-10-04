import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CampaignReview from './CampaignReview';
import type { ValidationResult } from './data';
import { errorResponse, makeCampaign, mockRoutes } from './test/helpers';

const CAMPAIGNS = [
  makeCampaign({ id: 1, name: 'Summer launch', platforms: ['Meta', 'Google'] }),
  makeCampaign({ id: 2, name: 'Course intake', platforms: ['Meta'] }),
];

function validation(overrides: Partial<ValidationResult> = {}): ValidationResult {
  return {
    campaign_id: 1,
    ready: true,
    errors: [],
    warnings: [],
    platform_checks: [
      { platform: 'Meta', ready: true, errors: [], warnings: [] },
      { platform: 'Google', ready: true, errors: [], warnings: [] },
    ],
    creative_count: 1,
    generated_content_ready: true,
    checked_at: '2026-03-24T09:00:00Z',
    ...overrides,
  };
}

const BLOCKED = validation({
  ready: false,
  errors: ['Attach at least one creative.'],
  platform_checks: [
    { platform: 'Meta', ready: true, errors: [], warnings: [] },
    { platform: 'Google', ready: false, errors: ['No connected Google account.'], warnings: [] },
  ],
  creative_count: 0,
  generated_content_ready: false,
});
function renderReview(campaigns = CAMPAIGNS) {
  const onConfirmed = vi.fn();
  render(<CampaignReview campaigns={campaigns} onConfirmed={onConfirmed} />);
  return { onConfirmed, user: userEvent.setup() };
}

describe('CampaignReview', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('explains that nothing publishes without review before running any check', () => {
    mockRoutes({});
    renderReview();

    expect(screen.getByText('Nothing publishes without your review')).toBeInTheDocument();
    expect(screen.getByText('User approval required')).toBeInTheDocument();
  });

  it('reports a ready campaign and enables confirmation', async () => {
    mockRoutes({ 'POST /api/v1/campaigns/1/validate': validation() });
    const { user } = renderReview();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));

    expect(await screen.findByText('Ready for publishing workflow')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Confirm review/ })).toBeEnabled();
  });

  it('reports a blocked campaign and disables confirmation', async () => {
    mockRoutes({ 'POST /api/v1/campaigns/1/validate': BLOCKED });
    const { user } = renderReview();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));

    expect(await screen.findByText('Campaign needs attention')).toBeInTheDocument();
    // Confirmation must be impossible while any check is failing.
    expect(screen.getByRole('button', { name: /Confirm review/ })).toBeDisabled();
  });

  it('lists per-platform readiness independently', async () => {
    mockRoutes({ 'POST /api/v1/campaigns/1/validate': BLOCKED });
    const { user } = renderReview();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));

    expect(await screen.findByText('1/2 platforms ready')).toBeInTheDocument();
    // Only per-platform messages are rendered; see the review-errors note in
    // ValidationResult: the campaign-level `errors` array is summarised by the
    // "Resolve the errors below" copy rather than listed item by item.
    expect(screen.getByText('No connected Google account.')).toBeInTheDocument();
    expect(screen.getByText('Resolve the errors below before confirming this campaign.')).toBeInTheDocument();
  });

  it('summarises creative and generated-content readiness', async () => {
    mockRoutes({ 'POST /api/v1/campaigns/1/validate': validation() });
    const { user } = renderReview();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));

    await screen.findByText('Ready for publishing workflow');
    expect(screen.getByText('Creatives attached')).toBeInTheDocument();
    expect(screen.getByText('Generated content')).toBeInTheDocument();
  });

  it('surfaces validation warnings without blocking confirmation', async () => {
    mockRoutes({
      'POST /api/v1/campaigns/1/validate': validation({ warnings: ['Landing page has no tracking pixel.'] }),
    });
    const { user } = renderReview();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));

    expect(await screen.findByText('Warnings to review')).toBeInTheDocument();
    expect(screen.getByText('Landing page has no tracking pixel.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Confirm review/ })).toBeEnabled();
  });

  it('confirms a ready campaign and tells the parent to continue', async () => {
    mockRoutes({
      'POST /api/v1/campaigns/1/validate': validation(),
      'POST /api/v1/campaigns/1/review/confirm': validation({ ready: true }),
    });
    const { onConfirmed, user } = renderReview();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));
    await user.click(await screen.findByRole('button', { name: /Confirm review/ }));

    await waitFor(() => expect(onConfirmed).toHaveBeenCalled());
  });

  it('reports a validation failure', async () => {
    mockRoutes({ 'POST /api/v1/campaigns/1/validate': errorResponse('Campaign not found.', 404) });
    const { user } = renderReview();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Campaign not found.');
  });

  it('reports a failed review confirmation without advancing', async () => {
    mockRoutes({
      'POST /api/v1/campaigns/1/validate': validation(),
      'POST /api/v1/campaigns/1/review/confirm': errorResponse('The campaign changed since validation.', 409),
    });
    const { onConfirmed, user } = renderReview();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));
    await user.click(await screen.findByRole('button', { name: /Confirm review/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The campaign changed since validation.');
    expect(onConfirmed).not.toHaveBeenCalled();
  });

  it('validates the newly selected campaign rather than the previous one', async () => {
    mockRoutes({
      'POST /api/v1/campaigns/1/validate': validation(),
      'POST /api/v1/campaigns/2/validate': validation({ campaign_id: 2 }),
    });
    // Read the installed mock rather than replacing it, so the route table stays
    // in effect and only the call log is inspected.
    const fetchMock = vi.mocked(fetch);
    const { user } = renderReview();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));
    await screen.findByText('Ready for publishing workflow');

    // Switching campaigns discards the previous result, so validation must be
    // re-run to prove the request targets the newly selected campaign.
    await user.selectOptions(screen.getByLabelText('Campaign'), '2');
    expect(screen.getByText('Nothing publishes without your review')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Run validation/ }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/api/v1/campaigns/2/validate', expect.objectContaining({ method: 'POST' })),
    );
  });
});