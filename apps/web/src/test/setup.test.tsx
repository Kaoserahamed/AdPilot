import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import StatusPill from '../StatusPill';

/**
 * Guards the test harness itself: if the jsdom environment or the testing-library
 * setup file stops loading, every component suite fails with a confusing DOM error.
 * This asserts the environment is genuinely usable.
 */
describe('test environment', () => {
  it('renders React components into a real DOM', () => {
    render(<StatusPill status="ACTIVE" />);

    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(document.body).not.toBeEmptyDOMElement();
  });

  it('cleans up rendered nodes between tests', () => {
    expect(document.body.innerHTML).toBe('');
  });
});