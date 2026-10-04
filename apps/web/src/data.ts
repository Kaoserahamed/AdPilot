/**
 * Static workspace data and navigation.
 *
 * Types live in `./types`, API transforms in `./mappers`, and display helpers in
 * `./formatters`. This module holds only literal data the shell renders before
 * any request completes.
 */

import type { ActivityEntry, Campaign, NavItem } from './types';

export const initialCampaigns: Campaign[] = [
  {
    id: 1,
    name: 'Summer launch \u00b7 Pro workspace',
    product: 'Pro workspace',
    description: 'Demo campaign',
    objective: 'sales',
    location: 'United States',
    audience: 'Founders',
    budget: 1500,
    currency: 'USD',
    durationDays: 30,
    landingPage: 'https://example.com',
    tone: 'Confident',
    platforms: ['Meta', 'Google'],
    status: 'Active',
    spend: 1248.6,
    createdAt: '2026-03-20T09:00:00Z',
    updatedAt: '2026-03-24T09:42:00Z',
  },
  {
    id: 2,
    name: 'Founders course \u00b7 Spring intake',
    product: 'Founders course',
    description: 'Demo campaign',
    objective: 'leads',
    location: 'Global',
    audience: 'Entrepreneurs',
    budget: 900,
    currency: 'USD',
    durationDays: 21,
    landingPage: 'https://example.com/course',
    tone: 'Expert',
    platforms: ['Google', 'YouTube'],
    status: 'Pending review',
    spend: 684.2,
    createdAt: '2026-03-19T09:00:00Z',
    updatedAt: '2026-03-23T16:18:00Z',
  },
  {
    id: 3,
    name: 'New collection awareness',
    product: 'Spring collection',
    description: 'Demo campaign',
    objective: 'brand_awareness',
    location: 'United States',
    audience: 'Design-conscious shoppers',
    budget: 600,
    currency: 'USD',
    durationDays: 14,
    landingPage: 'https://example.com/collection',
    tone: 'Casual',
    platforms: ['Meta'],
    status: 'Draft',
    spend: 0,
    createdAt: '2026-03-18T09:00:00Z',
    updatedAt: '2026-03-18T09:00:00Z',
  },
];

export const navItems: NavItem[] = [
  { label: 'Overview', icon: 'grid' },
  { label: 'Campaigns', icon: 'campaign' },
  { label: 'AI campaign studio', icon: 'spark' },
  { label: 'Review & validation', icon: 'check' },
  { label: 'Publishing', icon: 'external' },
  { label: 'Creative library', icon: 'library' },
  { label: 'Analytics', icon: 'analytics' },
  { label: 'Connected platforms', icon: 'platforms' },
];

export const activity: ActivityEntry[] = [
  ['spark', 'AI copy generated', 'Summer launch \u00b7 Meta ad 01', '12 min ago', 'violet'],
  ['check', 'Campaign submitted', 'Founders course \u00b7 Google Ads', '1 hr ago', 'green'],
  ['upload', 'Creative uploaded', 'spring-collection-hero.jpg', '3 hrs ago', 'blue'],
  ['pause', 'Campaign paused', 'New collection awareness', 'Yesterday', 'amber'],
];

// Re-exported so existing imports from './data' keep working while the module
// boundaries above become the canonical location.
export * from './types';
export * from './mappers';
export * from './formatters';