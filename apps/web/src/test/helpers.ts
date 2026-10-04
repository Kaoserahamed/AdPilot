import type { Campaign } from '../data';

/** Build a campaign with sensible defaults so tests only state what they assert on. */
export function makeCampaign(overrides: Partial<Campaign> = {}): Campaign {
  return {
    id: 1,
    name: 'Summer launch',
    product: 'Pro workspace',
    description: 'A campaign brief long enough to be realistic.',
    objective: 'sales',
    location: 'United States',
    audience: 'Founders',
    budget: 1500,
    currency: 'USD',
    durationDays: 30,
    landingPage: 'https://example.com',
    tone: 'Confident',
    offer: null,
    platforms: ['Meta'],
    status: 'DRAFT',
    spend: 0,
    createdAt: '2026-03-20T09:00:00Z',
    updatedAt: '2026-03-24T09:42:00Z',
    ...overrides,
  };
}

type RouteHandler = (body: BodyInit | null | undefined) => unknown;

/**
 * Install a `fetch` mock that answers by exact path.
 *
 * Handlers are matched on `METHOD path` first (for example `'POST /api/v1/campaigns'`),
 * then fall back to the bare path so a route can ignore the method. Unmatched
 * requests reject, which surfaces unexpected calls instead of hanging a test.
 */
export function mockRoutes(routes: Record<string, RouteHandler | unknown>): void {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const method = (init?.method ?? 'GET').toUpperCase();
    const handler = routes[`${method} ${path}`] ?? routes[path];

    if (handler === undefined) {
      return Promise.reject(new Error(`Unexpected request: ${method} ${path}`));
    }

    const resolved = typeof handler === 'function' ? (handler as RouteHandler)(init?.body ?? null) : handler;
    const status = 200;

    return Promise.resolve({
      ok: true,
      status,
      json: async () => resolved,
    } as unknown as Response);
  });

  vi.stubGlobal('fetch', fetchMock);
}

/** Build a failed `Response` carrying an API error detail. */
export function errorResponse(detail: string, status = 400): Response {
  return {
    ok: false,
    status,
    json: async () => ({ detail }),
  } as unknown as Response;
}