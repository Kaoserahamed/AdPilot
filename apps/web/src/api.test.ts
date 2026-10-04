import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiRequest } from './api';

/** Build a minimal `Response` stand-in for the mocked fetch. */
function jsonResponse(body: unknown, init: { status?: number } = {}): Response {
  const status = init.status ?? 200;
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe('apiRequest', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('returns the parsed body on success', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ id: 7, name: 'Launch' }));

    await expect(apiRequest('/api/v1/campaigns')).resolves.toEqual({ id: 7, name: 'Launch' });
  });

  it('sends credentials so the session cookie is included', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}));

    await apiRequest('/api/v1/campaigns');

    expect(fetch).toHaveBeenCalledWith('/api/v1/campaigns', expect.objectContaining({ credentials: 'include' }));
  });

  it('sets a JSON content type for requests without a form body', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}));

    await apiRequest('/api/v1/campaigns', { method: 'POST', body: JSON.stringify({ name: 'x' }) });

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init?.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('omits the JSON content type when the body is a FormData upload', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({}));
    const form = new FormData();
    form.append('file', new Blob(['x']), 'hero.png');

    await apiRequest('/api/v1/creatives', { method: 'POST', body: form });

    const [, init] = vi.mocked(fetch).mock.calls[0];
    // The browser must set the multipart boundary itself; overriding it corrupts the upload.
    expect(init?.headers).toBeUndefined();
  });

  it('throws the API detail message on an error response', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ detail: 'Authentication required' }, { status: 401 }));

    await expect(apiRequest('/api/v1/auth/me')).rejects.toThrow('Authentication required');
  });

  it('falls back to a generic message when the error body is unreadable', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error('not json');
      },
    } as unknown as Response);

    await expect(apiRequest('/api/v1/campaigns')).rejects.toThrow('Something went wrong. Please try again.');
  });

  it('returns undefined for a 204 No Content response', async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(undefined, { status: 204 }));

    await expect(apiRequest('/api/v1/auth/logout', { method: 'POST' })).resolves.toBeUndefined();
  });
});