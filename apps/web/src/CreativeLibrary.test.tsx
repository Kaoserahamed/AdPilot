import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CreativeLibrary from './CreativeLibrary';
import type { CreativeApi } from './data';
import { errorResponse, makeCampaign, mockRoutes } from './test/helpers';

const CAMPAIGNS = [makeCampaign({ id: 1, name: 'Summer launch' })];

function creative(overrides: Partial<CreativeApi> = {}): CreativeApi {
  return {
    id: 1,
    file_name: 'spring-collection-hero.jpg',
    file_url: '/api/v1/creatives/1/file',
    file_type: 'image',
    mime_type: 'image/jpeg',
    file_size: 2_400_000,
    width: 1200,
    height: 628,
    duration: null,
    created_at: '2026-03-24T09:00:00Z',
    campaign_ids: [],
    ...overrides,
  };
}

function renderLibrary(items: CreativeApi[] = [creative()], extra: Record<string, unknown> = {}) {
  mockRoutes({ '/api/v1/creatives': items, ...extra });
  render(<CreativeLibrary campaigns={CAMPAIGNS} />);
  return { user: userEvent.setup() };
}

describe('CreativeLibrary', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('shows a loading state while creatives are fetched', () => {
    mockRoutes({ '/api/v1/creatives': [creative()] });
    render(<CreativeLibrary campaigns={CAMPAIGNS} />);

    expect(screen.getByText(/Loading creative library/)).toBeInTheDocument();
  });

  it('lists the creatives returned by the API', async () => {
    renderLibrary();

    expect(await screen.findByText('spring-collection-hero.jpg')).toBeInTheDocument();
    expect(screen.getByText(/2\.3 MB/)).toBeInTheDocument();
  });

  it('prompts the user to upload when the library is empty', async () => {
    renderLibrary([]);

    expect(await screen.findByText('No creatives found')).toBeInTheDocument();
  });

  it('filters by creative type', async () => {
    const { user } = renderLibrary([
      creative({ id: 1, file_name: 'hero.jpg', file_type: 'image' }),
      creative({ id: 2, file_name: 'teaser.mp4', file_type: 'video' }),
    ]);

    await screen.findByText('hero.jpg');
    await user.click(screen.getByRole('button', { name: 'Video' }));

    expect(screen.getByText('teaser.mp4')).toBeInTheDocument();
    expect(screen.queryByText('hero.jpg')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'All assets' }));
    expect(screen.getByText('hero.jpg')).toBeInTheDocument();
  });

  it('searches by file name case-insensitively', async () => {
    const { user } = renderLibrary([
      creative({ id: 1, file_name: 'spring-collection-hero.jpg' }),
      creative({ id: 2, file_name: 'teaser.mp4' }),
    ]);

    await screen.findByText('spring-collection-hero.jpg');
    await user.type(screen.getByPlaceholderText('Search by file name'), 'TEASER');

    expect(screen.getByText('teaser.mp4')).toBeInTheDocument();
    expect(screen.queryByText('spring-collection-hero.jpg')).not.toBeInTheDocument();
  });

  it('shows an empty result when the search matches nothing', async () => {
    const { user } = renderLibrary();

    await screen.findByText('spring-collection-hero.jpg');
    await user.type(screen.getByPlaceholderText('Search by file name'), 'nothing-matches-this');

    expect(await screen.findByText('No creatives found')).toBeInTheDocument();
  });

  it('uploads a creative as multipart form data', async () => {
    const { user } = renderLibrary([], { 'POST /api/v1/creatives': creative({ id: 9, file_name: 'new-upload.png' }) });
    const fetchMock = vi.mocked(fetch);

    const file = new File(['binary'], 'new-upload.png', { type: 'image/png' });
    await user.upload(screen.getByLabelText(/Upload creative/), file);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    // The initial GET precedes the upload, so the POST is not the first call.
    const call = fetchMock.mock.calls.find(([url, init]) => url === '/api/v1/creatives' && init?.method === 'POST');
    expect(call).toBeDefined();
    // The multipart boundary must be left for the browser to set.
    expect(call?.[1]?.headers).toBeUndefined();
    expect(call?.[1]?.body).toBeInstanceOf(FormData);

    expect(await screen.findByText('new-upload.png')).toBeInTheDocument();
  });

  it('reports an upload failure', async () => {
    const { user } = renderLibrary([], { 'POST /api/v1/creatives': errorResponse('File exceeds the 25 MB limit.', 413) });

    const file = new File(['binary'], 'huge.png', { type: 'image/png' });
    await user.upload(screen.getByLabelText(/Upload creative/), file);

    expect(await screen.findByRole('alert')).toHaveTextContent('File exceeds the 25 MB limit.');
  });

  it('reports a failure to load the library', async () => {
    mockRoutes({ '/api/v1/creatives': errorResponse('Unable to load creatives.', 503) });
    render(<CreativeLibrary campaigns={CAMPAIGNS} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load creatives.');
  });

  it('attaches a creative to a campaign', async () => {
    const { user } = renderLibrary([creative()], {
      'POST /api/v1/creatives/1/attach': creative({ campaign_ids: [1] }),
    });
    const fetchMock = vi.mocked(fetch);

    await user.selectOptions(
      await screen.findByRole('combobox', { name: /Attach spring-collection-hero\.jpg to campaign/ }),
      '1',
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/creatives/1/attach',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ campaign_ids: [1] }) }),
    );
  });

  it('deletes a creative and removes it from the grid', async () => {
    const { user } = renderLibrary([creative()], { 'DELETE /api/v1/creatives/1': {} });

    await user.click(await screen.findByRole('button', { name: /Delete/ }));

    await waitFor(() => expect(screen.queryByText('spring-collection-hero.jpg')).not.toBeInTheDocument());
    expect(screen.getByText('No creatives found')).toBeInTheDocument();
  });
});