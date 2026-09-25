import { describe, expect, it } from 'vitest';
import { initialCampaigns } from './data';

describe('initial workspace data', () => {
  it('contains campaigns with stable lifecycle metadata', () => {
    expect(initialCampaigns).toHaveLength(3);
    expect(initialCampaigns.every((campaign) => campaign.name && campaign.product)).toBe(true);
    expect(initialCampaigns.map((campaign) => campaign.status)).toEqual(['Active', 'Pending review', 'Draft']);
  });
});
