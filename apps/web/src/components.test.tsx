import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Icon from './Icon';
import Metric from './Metric';
import StatusPill from './StatusPill';

describe('StatusPill', () => {
  it('renders the underscore-separated DRAFT status as a Draft label', () => {
    render(<StatusPill status="DRAFT" />);
    expect(screen.getByText('Draft')).toBeInTheDocument();
  });

  it('renders PENDING_REVIEW as Pending review', () => {
    render(<StatusPill status="PENDING_REVIEW" />);
    expect(screen.getByText('Pending review')).toBeInTheDocument();
  });

  it('title-cases other status values', () => {
    render(<StatusPill status="PUBLISHING" />);
    expect(screen.getByText('Publishing')).toBeInTheDocument();
  });

  it('leaves an already-formatted label untouched', () => {
    render(<StatusPill status="Active" />);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('derives a class name from the label so styles can target each state', () => {
    const { container } = render(<StatusPill status="PENDING_REVIEW" />);
    expect(container.querySelector('.status-pill.status-pending-review')).toBeInTheDocument();
  });

  it('renders a status dot alongside the label', () => {
    const { container } = render(<StatusPill status="FAILED" />);
    expect(container.querySelector('.status-dot')).toBeInTheDocument();
  });
});

describe('Metric', () => {
  it('renders the label, value, and change caption', () => {
    render(<Metric label="Total spend" value="$1,248.60" change="Last 30 days" accent="violet" icon="campaign" />);

    expect(screen.getByText('Total spend')).toBeInTheDocument();
    expect(screen.getByText('$1,248.60')).toBeInTheDocument();
    expect(screen.getByText('Last 30 days')).toBeInTheDocument();
  });

  it('applies the accent as a modifier class', () => {
    const { container } = render(<Metric label="Clicks" value="12" change="Reported" accent="green" icon="arrow" />);
    expect(container.querySelector('.metric-card.accent-green')).toBeInTheDocument();
  });

  it('renders the icon requested by the caller', () => {
    const { container } = render(<Metric label="Clicks" value="12" change="Reported" accent="green" icon="arrow" />);
    expect(container.querySelector('.metric-icon svg')).toBeInTheDocument();
  });
});

describe('Icon', () => {
  it('renders the requested icon as decorative markup', () => {
    const { container } = render(<Icon name="spark" />);
    const svg = container.querySelector('svg');

    expect(svg).toBeInTheDocument();
    // Decorative icons must stay out of the accessibility tree; the surrounding
    // control or text carries the meaning.
    expect(svg).toHaveAttribute('aria-hidden', 'true');
  });

  it('applies the requested size to width and height', () => {
    const { container } = render(<Icon name="spark" size={24} />);
    const svg = container.querySelector('svg');

    expect(svg).toHaveAttribute('width', '24');
    expect(svg).toHaveAttribute('height', '24');
  });

  it('defaults to a size of 18 when none is given', () => {
    const { container } = render(<Icon name="spark" />);
    expect(container.querySelector('svg')).toHaveAttribute('width', '18');
  });

  it('renders each navigation icon without error', () => {
    const names = ['grid', 'campaign', 'library', 'analytics', 'platforms', 'plus', 'arrow', 'spark', 'check', 'upload', 'pause', 'menu', 'close', 'chevron', 'external'];
    for (const name of names) {
      const { container, unmount } = render(<Icon name={name} />);
      expect(container.querySelector('svg')).toBeInTheDocument();
      unmount();
    }
  });
});