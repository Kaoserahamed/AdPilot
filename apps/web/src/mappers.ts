/**
 * Pure transformations between the API wire format and the shapes the UI uses.
 *
 * Keeping these separate from the type definitions means a change to a backend
 * field name is a one-line edit here, and these functions can be tested without
 * rendering anything.
 */

import type { AIGeneration, AIGenerationApi, Campaign, CampaignApi, Creative, CreativeApi } from './types';

export function toCampaign(campaign: CampaignApi): Campaign {
  return {
    id: campaign.id,
    name: campaign.name,
    product: campaign.product,
    description: campaign.description,
    objective: campaign.objective,
    location: campaign.location,
    audience: campaign.audience,
    budget: campaign.budget,
    currency: campaign.currency,
    durationDays: campaign.duration_days,
    landingPage: campaign.landing_page,
    tone: campaign.tone,
    offer: campaign.offer,
    platforms: campaign.platforms,
    status: campaign.status,
    spend: campaign.spend,
    createdAt: campaign.created_at,
    updatedAt: campaign.updated_at,
  };
}

export function toCreative(creative: CreativeApi): Creative {
  return {
    id: creative.id,
    fileName: creative.file_name,
    fileUrl: creative.file_url,
    fileType: creative.file_type,
    mimeType: creative.mime_type,
    fileSize: creative.file_size,
    width: creative.width,
    height: creative.height,
    duration: creative.duration,
    createdAt: creative.created_at,
    // Copied, not aliased: attaching or detaching a campaign mutates this list,
    // and the source object may still be held in component state.
    campaignIds: [...creative.campaign_ids],
  };
}

/**
 * Clone the nested structure so edits in the studio mutate the draft without
 * writing through to the cached generation object.
 */
export function toAIGeneration(value: AIGenerationApi): AIGeneration {
  return {
    ...value,
    content: {
      ...value.content,
      platform_ads: value.content.platform_ads.map((ad) => ({ ...ad })),
    },
  };
}