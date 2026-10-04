import { describe, expect, it } from 'vitest';
import { toAIGeneration, toCampaign, toCreative } from './mappers';
import type { AIGenerationApi, CampaignApi, CreativeApi } from './types';

const CAMPAIGN_API: CampaignApi = {
  id: 7,
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
  offer: '20% off',
  platforms: ['Meta', 'Google'],
  status: 'ACTIVE',
  spend: 1248.6,
  created_at: '2026-03-20T09:00:00Z',
  updated_at: '2026-03-24T09:42:00Z',
};

describe('toCampaign', () => {
  it('renames every snake_case field to camelCase', () => {
    const campaign = toCampaign(CAMPAIGN_API);

    expect(campaign.durationDays).toBe(30);
    expect(campaign.landingPage).toBe('https://example.com');
    expect(campaign.createdAt).toBe('2026-03-20T09:00:00Z');
    expect(campaign.updatedAt).toBe('2026-03-24T09:42:00Z');
  });

  it('carries through the fields whose names do not change', () => {
    const campaign = toCampaign(CAMPAIGN_API);

    expect(campaign).toMatchObject({
      id: 7,
      name: 'Summer launch',
      product: 'Pro workspace',
      objective: 'sales',
      location: 'United States',
      audience: 'Founders',
      budget: 1500,
      currency: 'USD',
      tone: 'Confident',
      offer: '20% off',
      platforms: ['Meta', 'Google'],
      status: 'ACTIVE',
      spend: 1248.6,
    });
  });

  it('preserves a null offer rather than coercing it', () => {
    expect(toCampaign({ ...CAMPAIGN_API, offer: null }).offer).toBeNull();
  });

  it('does not mutate the source payload', () => {
    const snapshot = { ...CAMPAIGN_API };
    toCampaign(CAMPAIGN_API);
    expect(CAMPAIGN_API).toEqual(snapshot);
  });
});

const CREATIVE_API: CreativeApi = {
  id: 3,
  file_name: 'spring-collection-hero.jpg',
  file_url: '/api/v1/creatives/3/file',
  file_type: 'image',
  mime_type: 'image/jpeg',
  file_size: 2_400_000,
  width: 1200,
  height: 628,
  duration: null,
  created_at: '2026-03-24T09:00:00Z',
  campaign_ids: [1, 2],
};

describe('toCreative', () => {
  it('renames every snake_case field to camelCase', () => {
    const creative = toCreative(CREATIVE_API);

    expect(creative.fileName).toBe('spring-collection-hero.jpg');
    expect(creative.fileUrl).toBe('/api/v1/creatives/3/file');
    expect(creative.fileType).toBe('image');
    expect(creative.mimeType).toBe('image/jpeg');
    expect(creative.fileSize).toBe(2_400_000);
    expect(creative.createdAt).toBe('2026-03-24T09:00:00Z');
    expect(creative.campaignIds).toEqual([1, 2]);
  });

  it('preserves null metadata for assets where dimensions are not known', () => {
    const creative = toCreative({ ...CREATIVE_API, width: null, height: null, duration: null });

    expect(creative.width).toBeNull();
    expect(creative.height).toBeNull();
    expect(creative.duration).toBeNull();
  });

  it('does not alias the campaign id array from the source payload', () => {
    const creative = toCreative(CREATIVE_API);
    creative.campaignIds.push(3);
    expect(CREATIVE_API.campaign_ids).toEqual([1, 2]);
  });
});

const GENERATION: AIGenerationApi = {
  id: 11,
  campaign_id: 1,
  provider: 'sandbox',
  model: 'deterministic',
  status: 'completed',
  content: {
    strategy: { objective: 'Drive signups', positioning: 'Built for small teams', channel_plan: ['Meta'] },
    audience: { primary: 'Founders', insights: ['Time poor'], locations: ['United States'] },
    messaging: { value_proposition: 'Ship faster', proof_points: [], tone: 'Confident', call_to_action: 'Start free' },
    platform_ads: [{ platform: 'Meta', headline: 'One brief', description: 'Every channel', cta: 'Start free' }],
  },
  created_at: '2026-03-24T09:00:00Z',
};

describe('toAIGeneration', () => {
  it('preserves the generation metadata', () => {
    const generation = toAIGeneration(GENERATION);

    expect(generation.id).toBe(11);
    expect(generation.campaign_id).toBe(1);
    expect(generation.provider).toBe('sandbox');
    expect(generation.status).toBe('completed');
  });

  it('deep-clones the platform ads so editing a draft cannot mutate the cached generation', () => {
    const generation = toAIGeneration(GENERATION);
    generation.content.platform_ads[0].headline = 'Edited';

    expect(GENERATION.content.platform_ads[0].headline).toBe('One brief');
  });

  it('copies every ad in the array rather than only the first', () => {
    const withTwoAds: AIGenerationApi = {
      ...GENERATION,
      content: {
        ...GENERATION.content,
        platform_ads: [
          { platform: 'Meta', headline: 'Meta headline', description: 'd', cta: 'c' },
          { platform: 'Google', headline: 'Google headline', description: 'd', cta: 'c' },
        ],
      },
    };

    const generation = toAIGeneration(withTwoAds);
    generation.content.platform_ads[1].headline = 'Edited';

    expect(withTwoAds.content.platform_ads[1].headline).toBe('Google headline');
  });
});