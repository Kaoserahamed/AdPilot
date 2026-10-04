import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CreateModal from './CreateModal';
import type { CampaignApi } from './data';
import { errorResponse } from './test/helpers';

const CAMPAIGN_API: CampaignApi = {
  id: 42,
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
  status: 'DRAFT',
  spend: 0,
  created_at: '2026-03-24T09:00:00Z',
  updated_at: '2026-03-24T09:00:00Z',
};

function renderModal() {
  const onClose = vi.fn();
  const onCreated = vi.fn();
  render(<CreateModal onClose={onClose} onCreated={onCreated} />);
  return { onClose, onCreated, user: userEvent.setup() };
}

/** Fill every required field so the form can submit. */
async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Campaign name'), 'Summer launch');
  await user.type(screen.getByLabelText('Product or service'), 'Pro workspace');
  await user.type(screen.getByLabelText('Description'), 'A workspace for growing teams.');
  await user.type(screen.getByLabelText('Target location'), 'United States');
  await user.type(screen.getByLabelText('Target audience'), 'Founders');
  await user.type(screen.getByLabelText('Budget (USD)'), '1500');
  await user.type(screen.getByLabelText('Landing page URL'), 'https://example.com');
}

function createdCampaign() {
  return { ok: true, status: 201, json: async () => CAMPAIGN_API } as unknown as Response;
}

describe('CreateModal', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders as a labelled modal dialog', () => {
    renderModal();

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByRole('heading', { name: 'Create your campaign' })).toBeInTheDocument();
  });

  it('creates a campaign and reports it back with camelCase fields', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(createdCampaign()));
    const { onCreated, user } = renderModal();

    await fillRequiredFields(user);
    await user.click(screen.getByRole('button', { name: /Create campaign/ }));

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    // The component normalises the snake_case API payload before handing it up.
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: 42, durationDays: 30, landingPage: 'https://example.com' }));
  });

  it('sends the brief as JSON in the shape the API expects', async () => {
    const fetchMock = vi.fn().mockResolvedValue(createdCampaign());
    vi.stubGlobal('fetch', fetchMock);
    const { user } = renderModal();

    await fillRequiredFields(user);
    await user.selectOptions(screen.getByLabelText('Objective'), 'leads');
    await user.click(screen.getByRole('button', { name: /Create campaign/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe('/api/v1/campaigns');

    const payload = JSON.parse(init.body as string);
    expect(payload).toMatchObject({
      name: 'Summer launch',
      product: 'Pro workspace',
      objective: 'leads',
      location: 'United States',
      audience: 'Founders',
      budget: 1500,
      landing_page: 'https://example.com',
      duration_days: 30,
    });
    // Meta is checked by default; the form must send it as an array.
    expect(payload.platforms).toEqual(['Meta']);
  });

  it('normalises an empty optional offer to null rather than an empty string', async () => {
    const fetchMock = vi.fn().mockResolvedValue(createdCampaign());
    vi.stubGlobal('fetch', fetchMock);
    const { user } = renderModal();

    await fillRequiredFields(user);
    await user.click(screen.getByRole('button', { name: /Create campaign/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string).offer).toBeNull();
  });

  it('collects every selected platform', async () => {
    const fetchMock = vi.fn().mockResolvedValue(createdCampaign());
    vi.stubGlobal('fetch', fetchMock);
    const { user } = renderModal();

    await fillRequiredFields(user);
    await user.click(screen.getByLabelText('Google'));
    await user.click(screen.getByLabelText('YouTube'));
    await user.click(screen.getByRole('button', { name: /Create campaign/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string).platforms).toEqual(['Meta', 'Google', 'YouTube']);
  });

  it('keeps the modal open and shows the API error when creation fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(errorResponse('Landing page must be a valid URL.', 422)));
    const { onCreated, user } = renderModal();

    await fillRequiredFields(user);
    await user.click(screen.getByRole('button', { name: /Create campaign/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Landing page must be a valid URL.');
    expect(onCreated).not.toHaveBeenCalled();
  });

  it('does not close when a click lands inside the dialog', async () => {
    const { onClose, user } = renderModal();

    await user.click(screen.getByRole('heading', { name: 'Create your campaign' }));

    // The handler only fires for a click on the backdrop itself.
    expect(onClose).not.toHaveBeenCalled();
  });

  it('closes from the cancel button without creating anything', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const { onClose, onCreated, user } = renderModal();

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onClose).toHaveBeenCalled();
    expect(onCreated).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('closes from the close icon', async () => {
    const { onClose, user } = renderModal();

    await user.click(screen.getByRole('button', { name: 'Close' }));

    expect(onClose).toHaveBeenCalled();
  });
});