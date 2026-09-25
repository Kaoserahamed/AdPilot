import { useEffect, useState } from 'react';
import { apiRequest } from './api';
import { toAIGeneration, type AIContent, type AIGeneration, type AIGenerationApi, type Campaign } from './data';
import Icon from './Icon';

type Props = { campaigns: Campaign[] };
const emptyContent: AIContent = { strategy: { objective: '', positioning: '', channel_plan: [] }, audience: { primary: '', insights: [], locations: [] }, messaging: { value_proposition: '', proof_points: [], tone: '', call_to_action: '' }, platform_ads: [] };

export default function AIStudio({ campaigns }: Props) {
  const [campaignId, setCampaignId] = useState(campaigns[0]?.id ?? 0);
  const [generation, setGeneration] = useState<AIGeneration | null>(null);
  const [draft, setDraft] = useState<AIContent>(emptyContent);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!campaignId) return;
    apiRequest<AIGenerationApi>(`/api/v1/ai/campaigns/${campaignId}/generation`).then((value) => { const next = toAIGeneration(value); setGeneration(next); setDraft(next.content); }).catch(() => { setGeneration(null); setDraft(emptyContent); });
  }, [campaignId]);

  const request = async (path: string, body: object, method: 'POST' | 'PUT' = 'POST') => {
    setBusy(true); setError('');
    try { const next = toAIGeneration(await apiRequest<AIGenerationApi>(path, { method, body: JSON.stringify(body) })); setGeneration(next); setDraft(next.content); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'AI request failed.'); }
    finally { setBusy(false); }
  };
  const edit = (action: string, value?: string) => generation && request('/api/v1/ai/edit', { campaign_id: campaignId, platform: generation.content.platform_ads[0]?.platform ?? 'Meta', action, value });
  const save = () => generation && request(`/api/v1/ai/generations/${generation.id}`, { content: draft }, 'PUT');
  const updateAd = (index: number, field: string, value: string) => setDraft((current) => ({ ...current, platform_ads: current.platform_ads.map((ad, adIndex) => adIndex === index ? { ...ad, [field]: value } : ad) }));

  return <section className="ai-studio"><div className="ai-studio-header"><div><p className="eyebrow">AI campaign copilot</p><h1>Review your campaign</h1><p className="subtitle">Generate, refine, and review platform-specific content before publishing.</p></div><span className="review-badge"><Icon name="spark" size={15} />Review only</span></div><div className="ai-toolbar"><label>Campaign<select value={campaignId} onChange={(event) => setCampaignId(Number(event.target.value))}><option value={0}>Select a campaign</option>{campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}</select></label><div className="ai-actions"><button className="button button-secondary" disabled={!campaignId || busy} onClick={() => request('/api/v1/ai/generate-campaign', { campaign_id: campaignId })}>{generation ? 'Regenerate' : 'Generate content'}</button>{generation && <button className="button button-primary" disabled={busy} onClick={save}>Save review</button>}</div></div>{error && <div className="auth-message error" role="alert">{error}</div>}{campaigns.length === 0 ? <div className="library-empty"><div><Icon name="campaign" size={24} /></div><strong>Create a campaign first</strong><span>AI content is always attached to a campaign brief.</span></div> : !generation ? <div className="ai-empty"><div className="ai-empty-icon"><Icon name="spark" size={25} /></div><h2>Turn your brief into channel-ready content</h2><p>AdPilot will create a strategy, audience profile, messaging, and platform-specific ad copy for you.</p><button className="button button-primary" disabled={!campaignId || busy} onClick={() => request('/api/v1/ai/generate-campaign', { campaign_id: campaignId })}>Generate campaign content <Icon name="arrow" size={16} /></button></div> : <><div className="ai-summary-grid"><article className="ai-summary-card"><span>Objective</span><strong>{draft.strategy.objective}</strong><p>{draft.strategy.positioning}</p></article><article className="ai-summary-card"><span>Audience</span><strong>{draft.audience.primary}</strong><p>{draft.audience.insights.join(' · ')}</p></article><article className="ai-summary-card"><span>Messaging</span><strong>{draft.messaging.tone}</strong><p>{draft.messaging.value_proposition}</p></article></div><div className="ai-content-header"><div><h2>Platform versions</h2><p>Edit the copy directly. Nothing publishes without your confirmation.</p></div><div className="ai-edit-actions"><button onClick={() => edit('shorten')}>Shorten</button><button onClick={() => edit('expand')}>Expand</button><button onClick={() => edit('professional')}>Professional</button><button onClick={() => edit('casual')}>Casual</button></div></div><div className="ai-ad-grid">{draft.platform_ads.map((ad, index) => <article className="ai-ad-card" key={`${ad.platform}-${index}`}><div className="ai-ad-card-header"><span className={`platform-badge platform-${ad.platform.toLowerCase()}`}>{ad.platform}</span><span>Generated content</span></div>{ad.primary_text !== undefined && <label>Primary text<textarea value={ad.primary_text} onChange={(event) => updateAd(index, 'primary_text', event.target.value)} /></label>}<label>Headline<input value={ad.headline} onChange={(event) => updateAd(index, 'headline', event.target.value)} /></label>{ad.long_headline && <label>Long headline<input value={ad.long_headline} onChange={(event) => updateAd(index, 'long_headline', event.target.value)} /></label>}<label>Description<textarea value={ad.description} onChange={(event) => updateAd(index, 'description', event.target.value)} /></label>{ad.video_hook && <label>Video hook<textarea value={ad.video_hook} onChange={(event) => updateAd(index, 'video_hook', event.target.value)} /></label>}{ad.video_script && <label>Video script<textarea value={ad.video_script} onChange={(event) => updateAd(index, 'video_script', event.target.value)} /></label>}<label>Call to action<input value={ad.cta} onChange={(event) => updateAd(index, 'cta', event.target.value)} /></label><div className="ai-ad-footer"><button onClick={() => edit('change_cta', ad.cta === 'Learn more' ? 'Get started' : 'Learn more')}>Change CTA</button><span>Review before publishing</span></div></article>)}</div></>}</section>;
}
