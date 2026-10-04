import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AIStudio from './AIStudio';
import type { AIGenerationApi } from './data';
import { errorResponse, makeCampaign, mockRoutes } from './test/helpers';

const CAMPAIGNS = [makeCampaign({ id: 1, name: 'Summer launch' })];

const CONTENT = {
  strategy: { objective: 'Drive trial signups', positioning: 'The workspace built for small teams', channel_plan: ['Meta', 'Google'] },
  audience: { primary: 'Early-stage founders', insights: ['Time poor', 'Budget conscious'], locations: ['United States'] },
  messaging: { value_proposition: 'Ship campaigns in an afternoon', proof_points: ['Used by 2,000 teams'], tone: 'Confident', call_to_action: 'Start free' },
  platform_ads: [
    { platform: 'Meta' as const, primary_text: 'Grow faster with AdPilot.', headline: 'Your campaigns, one brief', description: 'Review before you spend.', cta: 'Start free' },
  ],
};

const GENERATION: AIGenerationApi = {
  id: 11,
  campaign_id: 1,
  provider: 'sandbox',
  model: 'deterministic',
  status: 'completed',
  content: CONTENT,
  created_at: '2026-03-24T09:00:00Z',
};

function renderStudio(extra: Record<string, unknown> = {}, campaigns = CAMPAIGNS) {
  mockRoutes({ '/api/v1/ai/campaigns/1/generation': GENERATION, ...extra });
  render(<AIStudio campaigns={campaigns} />);
  return { user: userEvent.setup() };
}

describe('AIStudio', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('prompts the user to create a campaign before generating content', () => {
    renderStudio({}, []);
    expect(screen.getByText('Create a campaign first')).toBeInTheDocument();
  });

  it('offers generation when the campaign has no content yet', () => {
    mockRoutes({ '/api/v1/ai/campaigns/1/generation': errorResponse('No generation found.', 404) });
    render(<AIStudio campaigns={CAMPAIGNS} />);

    expect(screen.getByText('Turn your brief into channel-ready content')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Generate campaign content/ })).toBeInTheDocument();
  });

  it('renders the existing generation for the selected campaign', async () => {
    renderStudio();

    expect(await screen.findByText('Drive trial signups')).toBeInTheDocument();
    expect(screen.getByText('Early-stage founders')).toBeInTheDocument();
    expect(screen.getByText('Grow faster with AdPilot.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save review' })).toBeInTheDocument();
  });

  it('labels itself as review-only so nothing reads as auto-published', async () => {
    renderStudio();
    expect(await screen.findByText('Review only')).toBeInTheDocument();
  });

  it('generates content for the selected campaign', async () => {
    mockRoutes({
      '/api/v1/ai/campaigns/1/generation': errorResponse('No generation found.', 404),
      'POST /api/v1/ai/generate-campaign': GENERATION,
    });
    const fetchMock = vi.mocked(fetch);
    render(<AIStudio campaigns={CAMPAIGNS} />);
    const user = userEvent.setup();

    // The toolbar and the empty state each render a generate control.
    await user.click((await screen.findAllByRole('button', { name: /Generate campaign content/ }))[0]);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/ai/generate-campaign',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ campaign_id: 1 }) }),
    );
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save review' })).toBeInTheDocument());
  });

  it('reports a generation failure', async () => {
    mockRoutes({
      '/api/v1/ai/campaigns/1/generation': errorResponse('No generation found.', 404),
      'POST /api/v1/ai/generate-campaign': errorResponse('The AI provider is not configured.', 503),
    });
    render(<AIStudio campaigns={CAMPAIGNS} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: /Generate campaign content/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The AI provider is not configured.');
  });

  it('lets the user edit generated copy directly before saving', async () => {
    renderStudio();
    const user = userEvent.setup();

    const headline = await screen.findByLabelText('Headline');
    await user.clear(headline);
    await user.type(headline, 'Edited headline');

    expect(headline).toHaveValue('Edited headline');
  });

  it('saves the reviewed content back to the generation', async () => {
    renderStudio({ 'PUT /api/v1/ai/generations/11': { ...GENERATION, content: CONTENT } });
    const fetchMock = vi.mocked(fetch);
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Save review' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/ai/generations/11',
      expect.objectContaining({ method: 'PUT' }),
    );
  });

  it('applies a tone edit to the first platform ad', async () => {
    const { user } = renderStudio({ 'POST /api/v1/ai/edit': GENERATION });
    const fetchMock = vi.mocked(fetch);

    await user.click(await screen.findByRole('button', { name: 'Shorten' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const call = fetchMock.mock.calls.find(([url]) => url === '/api/v1/ai/edit');
    expect(call).toBeDefined();
    expect(JSON.parse((call?.[1]?.body as string) ?? '{}')).toMatchObject({
      campaign_id: 1,
      platform: 'Meta',
      action: 'shorten',
    });
  });

  it('surfaces per-platform ad badges so channels are distinguishable', async () => {
    renderStudio();
    expect(await screen.findByText('Platform versions')).toBeInTheDocument();
    expect(screen.getAllByText('Meta').length).toBeGreaterThan(0);
  });
});