import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AuthScreen from './AuthScreen';
import { errorResponse } from './test/helpers';

const USER = { id: 1, name: 'Alex Morgan', email: 'alex@example.com' };

function renderScreen(apiError: string | null = null) {
  const onAuthenticated = vi.fn();
  render(<AuthScreen onAuthenticated={onAuthenticated} apiError={apiError} />);
  return { onAuthenticated, user: userEvent.setup() };
}

describe('AuthScreen', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('starts in login mode with no password confirmation field', () => {
    renderScreen();

    expect(screen.getByRole('heading', { name: 'Welcome back.' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email address')).toBeInTheDocument();
    expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument();
  });

  it('signs in and hands the authenticated user to the parent', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => USER } as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { onAuthenticated, user } = renderScreen();

    await user.type(screen.getByLabelText('Email address'), 'alex@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: 'Sign in to AdPilot' }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith(USER));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/login', expect.objectContaining({ method: 'POST' }));
  });

  it('switches to register mode and exposes the name field', async () => {
    const { user } = renderScreen();

    await user.click(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.getByRole('heading', { name: 'Start making ads smarter.' })).toBeInTheDocument();
    expect(screen.getByLabelText('Full name')).toBeInTheDocument();
  });

  it('registers through the register endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 201, json: async () => USER } as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { onAuthenticated, user } = renderScreen();

    await user.click(screen.getByRole('button', { name: 'Create account' }));
    await user.type(screen.getByLabelText('Full name'), 'Alex Morgan');
    await user.type(screen.getByLabelText('Email address'), 'alex@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: /Create my workspace/ }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith(USER));
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/register', expect.objectContaining({ method: 'POST' }));
  });

  it('surfaces the API error message on a failed login', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(errorResponse('Incorrect email or password.', 401)));
    const { user } = renderScreen();

    await user.type(screen.getByLabelText('Email address'), 'alex@example.com');
    await user.type(screen.getByLabelText('Password'), 'wrong-password-here');
    await user.click(screen.getByRole('button', { name: 'Sign in to AdPilot' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.');
  });

  it('displays an API-level error passed down from the app shell', () => {
    renderScreen('Unable to reach the AdPilot API.');
    expect(screen.getByRole('alert')).toHaveTextContent('Unable to reach the AdPilot API.');
  });

  it('does not reveal whether an account exists during a password reset', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => undefined } as unknown as Response);
    vi.stubGlobal('fetch', fetchMock);
    const { user } = renderScreen();

    await user.click(screen.getByRole('button', { name: 'Forgot your password?' }));
    await user.type(screen.getByLabelText('Email address'), 'alex@example.com');
    await user.click(screen.getByRole('button', { name: /Send reset instructions/ }));

    expect(await screen.findByRole('status')).toHaveTextContent('If an account exists, check your email for reset instructions.');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/auth/password-reset/request', expect.objectContaining({ method: 'POST' }));
  });

  it('clears the typed password when switching between modes', async () => {
    const { user } = renderScreen();

    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery');
    await user.click(screen.getByRole('button', { name: 'Create account' }));

    expect(screen.getByLabelText('Password')).toHaveValue('');
  });
});