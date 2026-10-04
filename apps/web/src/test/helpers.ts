import { vi } from 'vitest';
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
 * then fall back to the bare path so a route can ignore the method. A handler may
 * return an {@link errorResponse} to exercise a failure path, or throw to simulate a
 * transport failure. Unmatched requests reject, which surfaces unexpected calls
 * instead of hanging a test.
 */
export function mockRoutes(routes: Record<string, RouteHandler | unknown>): void {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const method = (init?.method ?? 'GET').toUpperCase();
    const handler = routes[`${method} ${path}`] ?? routes[path];

    if (handler === undefined) {
      return Promise.reject(new Error(`Unexpected request: ${method} ${path}`));
    }

    if (typeof handler === 'function') {
      return Promise.resolve((handler as RouteHandler)(init?.body ?? null) as Response);
    }

    if (isErrorRoute(handler)) {
      return Promise.resolve(handler.value);
    }

    return Promise.resolve({
      ok: true,
      status: 200,
      json: async () => handler,
    } as unknown as Response);
  });

  vi.stubGlobal('fetch', fetchMock);
}

/** Marker produced by {@link errorResponse} so a mock route can return a failure. */
type ErrorRoute = { readonly __errorRoute: true; readonly value: Response };

function isErrorRoute(value: unknown): value is ErrorRoute {
  return typeof value === 'object' && value !== null && '__errorRoute' in value;
}

/**
 * Build a failed response carrying an API error detail.
 *
 * The value is tagged rather than returned as a bare `Response` cast, because the
 * mock routes cannot rely on `instanceof` surviving across module boundaries.
 */
export function errorResponse(detail: string, status = 400): ErrorRoute {
  return {
    __errorRoute: true,
    value: {
      ok: false,
      status,
      json: async () => ({ detail }),
    } as unknown as Response,
  };
}