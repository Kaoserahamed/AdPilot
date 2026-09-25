export type CampaignStatus = 'Active' | 'Draft' | 'Pending review' | string;

export type Campaign = {
  id: number;
  name: string;
  product: string;
  description: string;
  objective: string;
  location: string;
  audience: string;
  budget: number;
  currency: string;
  durationDays: number;
  landingPage: string;
  tone: string;
  offer?: string | null;
  platforms: string[];
  status: CampaignStatus;
  spend: number;
  createdAt: string;
  updatedAt: string;
};

export const initialCampaigns: Campaign[] = [
  { id: 1, name: 'Summer launch · Pro workspace', product: 'Pro workspace', description: 'Demo campaign', objective: 'sales', location: 'United States', audience: 'Founders', budget: 1500, currency: 'USD', durationDays: 30, landingPage: 'https://example.com', tone: 'Confident', platforms: ['Meta', 'Google'], status: 'Active', spend: 1248.6, createdAt: '2026-03-20T09:00:00Z', updatedAt: '2026-03-24T09:42:00Z' },
  { id: 2, name: 'Founders course · Spring intake', product: 'Founders course', description: 'Demo campaign', objective: 'leads', location: 'Global', audience: 'Entrepreneurs', budget: 900, currency: 'USD', durationDays: 21, landingPage: 'https://example.com/course', tone: 'Expert', platforms: ['Google', 'YouTube'], status: 'Pending review', spend: 684.2, createdAt: '2026-03-19T09:00:00Z', updatedAt: '2026-03-23T16:18:00Z' },
  { id: 3, name: 'New collection awareness', product: 'Spring collection', description: 'Demo campaign', objective: 'brand_awareness', location: 'United States', audience: 'Design-conscious shoppers', budget: 600, currency: 'USD', durationDays: 14, landingPage: 'https://example.com/collection', tone: 'Casual', platforms: ['Meta'], status: 'Draft', spend: 0, createdAt: '2026-03-18T09:00:00Z', updatedAt: '2026-03-18T09:00:00Z' },
];

export type CampaignApi = {
  id: number;
  name: string;
  product: string;
  description: string;
  objective: string;
  location: string;
  audience: string;
  budget: number;
  currency: string;
  duration_days: number;
  landing_page: string;
  tone: string;
  offer?: string | null;
  platforms: string[];
  status: string;
  spend: number;
  created_at: string;
  updated_at: string;
};

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

export function formatSpend(campaign: Campaign): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: campaign.currency || 'USD' }).format(campaign.spend);
}

export function formatUpdated(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}


export type CreativeType = 'image' | 'video' | 'logo';
export type Creative = { id: number; fileName: string; fileUrl: string; fileType: CreativeType; mimeType: string; fileSize: number; width: number | null; height: number | null; duration: number | null; createdAt: string; campaignIds: number[] };
export type CreativeApi = { id: number; file_name: string; file_url: string; file_type: CreativeType; mime_type: string; file_size: number; width: number | null; height: number | null; duration: number | null; created_at: string; campaign_ids: number[] };
export function toCreative(creative: CreativeApi): Creative { return { id: creative.id, fileName: creative.file_name, fileUrl: creative.file_url, fileType: creative.file_type, mimeType: creative.mime_type, fileSize: creative.file_size, width: creative.width, height: creative.height, duration: creative.duration, createdAt: creative.created_at, campaignIds: creative.campaign_ids }; }
export function formatBytes(bytes: number): string { if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`; return `${(bytes / (1024 * 1024)).toFixed(1)} MB`; }

export type AIPlatformAd = { platform: 'Meta' | 'Google' | 'YouTube'; primary_text?: string; headline: string; long_headline?: string; description: string; video_hook?: string; video_script?: string; cta: string };
export type AIContent = { strategy: { objective: string; positioning: string; channel_plan: string[] }; audience: { primary: string; insights: string[]; locations: string[] }; messaging: { value_proposition: string; proof_points: string[]; tone: string; call_to_action: string }; platform_ads: AIPlatformAd[] };
export type AIGeneration = { id: number; campaign_id: number; provider: string; model: string; status: string; content: AIContent; created_at: string };
export type AIGenerationApi = { id: number; campaign_id: number; provider: string; model: string; status: string; content: AIContent; created_at: string };
export function toAIGeneration(value: AIGenerationApi): AIGeneration { return { ...value, content: { ...value.content, platform_ads: value.content.platform_ads.map((ad) => ({ ...ad })) } }; }

export type PlatformCapability = { platform: string; label: string; connected: boolean; supports_oauth: boolean; supports_video: boolean; supports_metrics: boolean; supports_pause: boolean; sandbox: boolean };
export type ConnectedAccount = { id: number; platform: string; platform_label: string; external_account_id: string; name: string; currency: string; status: string; connected_at: string; sandbox: boolean };



export const navItems = [
  { label: 'Overview', icon: 'grid' },
  { label: 'Campaigns', icon: 'campaign', count: 3 },
  { label: 'AI campaign studio', icon: 'spark' },

  { label: 'Creative library', icon: 'library' },
  { label: 'Analytics', icon: 'analytics' },
  { label: 'Connected platforms', icon: 'platforms' },
];

export const activity = [
  ['spark', 'AI copy generated', 'Summer launch · Meta ad 01', '12 min ago', 'violet'],
  ['check', 'Campaign submitted', 'Founders course · Google Ads', '1 hr ago', 'green'],
  ['upload', 'Creative uploaded', 'spring-collection-hero.jpg', '3 hrs ago', 'blue'],
  ['pause', 'Campaign paused', 'New collection awareness', 'Yesterday', 'amber'],
] as const;
