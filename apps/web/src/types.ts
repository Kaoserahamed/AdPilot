/**
 * Shared domain types for the AdPilot workspace.
 *
 * These mirror the FastAPI response models in `apps/api/app`. Anything suffixed
 * `Api` is the wire shape returned by the backend (snake_case); the matching
 * type without the suffix is the camelCase shape the UI works with. The mapping
 * between the two lives in `mappers.ts`.
 */

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

export type CreativeType = 'image' | 'video' | 'logo';

export type Creative = {
  id: number;
  fileName: string;
  fileUrl: string;
  fileType: CreativeType;
  mimeType: string;
  fileSize: number;
  width: number | null;
  height: number | null;
  duration: number | null;
  createdAt: string;
  campaignIds: number[];
};

export type CreativeApi = {
  id: number;
  file_name: string;
  file_url: string;
  file_type: CreativeType;
  mime_type: string;
  file_size: number;
  width: number | null;
  height: number | null;
  duration: number | null;
  created_at: string;
  campaign_ids: number[];
};

export type AIPlatformAd = {
  platform: 'Meta' | 'Google' | 'YouTube';
  primary_text?: string;
  headline: string;
  long_headline?: string;
  description: string;
  video_hook?: string;
  video_script?: string;
  cta: string;
};

export type AIContent = {
  strategy: { objective: string; positioning: string; channel_plan: string[] };
  audience: { primary: string; insights: string[]; locations: string[] };
  messaging: { value_proposition: string; proof_points: string[]; tone: string; call_to_action: string };
  platform_ads: AIPlatformAd[];
};

export type AIGeneration = {
  id: number;
  campaign_id: number;
  provider: string;
  model: string;
  status: string;
  content: AIContent;
  created_at: string;
};

export type AIGenerationApi = AIGeneration;

export type PlatformCapability = {
  platform: string;
  label: string;
  connected: boolean;
  supports_oauth: boolean;
  supports_video: boolean;
  supports_metrics: boolean;
  supports_pause: boolean;
  sandbox: boolean;
};

export type ConnectedAccount = {
  id: number;
  platform: string;
  platform_label: string;
  external_account_id: string;
  name: string;
  currency: string;
  status: string;
  connected_at: string;
  sandbox: boolean;
};

export type PlatformCheck = {
  platform: string;
  ready: boolean;
  errors: string[];
  warnings: string[];
};

export type ValidationResult = {
  campaign_id: number;
  ready: boolean;
  errors: string[];
  warnings: string[];
  platform_checks: PlatformCheck[];
  creative_count: number;
  generated_content_ready: boolean;
  checked_at: string;
};

export type PublishingJob = {
  id: number;
  campaign_id: number;
  status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';
  attempt: number;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type PlatformCampaign = {
  id: number;
  platform: string;
  external_campaign_id: string;
  status: string;
  detail: string | null;
  updated_at: string;
};

export type CampaignStatusResult = {
  campaign_id: number;
  status: string;
  updated_at: string;
  platforms: PlatformCampaign[];
  jobs: PublishingJob[];
};

export type PublishResponse = {
  campaign_id: number;
  status: string;
  job: PublishingJob;
  message: string;
};

export type PlatformBreakdown = {
  platform: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  ctr: number | null;
  cpc: number | null;
  cpa: number | null;
  roas: number | null;
  currency: string;
  calculated_fields: string[];
};

export type CampaignAnalytics = {
  campaign_id: number;
  campaign_name: string;
  status: string;
  reporting_period_days: number;
  platforms: PlatformBreakdown[];
  totals: { spend: number; impressions: number; clicks: number; conversions: number };
  calculated_fields: string[];
  synced_at: string | null;
};

export type AnalyticsOverview = {
  reporting_period_days: number;
  active_campaigns: number;
  draft_campaigns: number;
  pending_review_campaigns: number;
  total_spend: number;
  total_impressions: number;
  total_clicks: number;
  total_conversions: number;
  currency: string;
  calculated_fields: string[];
  platforms: PlatformBreakdown[];
  campaigns: CampaignAnalytics[];
};

export type MetricLine = {
  metric: string;
  value: number;
  currency: string;
  source: string;
  calculated: boolean;
  reported_at: string;
};

export type AnalysisAnswer = {
  campaign_id: number;
  question: string;
  period_start: string;
  period_end: string;
  summary: string;
  highlights: string[];
  facts: MetricLine[];
  data_complete: boolean;
  unavailable: string[];
  provider: string;
  model: string;
};

export type NavItem = { label: string; icon: string };

export type ActivityEntry = readonly [string, string, string, string, string];