export type CampaignStatus = 'Active' | 'Draft' | 'Pending review';

export type Campaign = {
  name: string;
  product: string;
  platforms: string[];
  status: CampaignStatus;
  spend: string;
  updated: string;
};

export const initialCampaigns: Campaign[] = [
  { name: 'Summer launch · Pro workspace', product: 'Pro workspace', platforms: ['Meta', 'Google'], status: 'Active', spend: '$1,248.60', updated: 'Today, 9:42 AM' },
  { name: 'Founders course · Spring intake', product: 'Founders course', platforms: ['Google', 'YouTube'], status: 'Pending review', spend: '$684.20', updated: 'Yesterday, 4:18 PM' },
  { name: 'New collection awareness', product: 'Spring collection', platforms: ['Meta'], status: 'Draft', spend: '$0.00', updated: 'Mar 18, 2026' },
];

export const navItems = [
  { label: 'Overview', icon: 'grid' },
  { label: 'Campaigns', icon: 'campaign', count: 3 },
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
