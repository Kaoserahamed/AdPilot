import { useState, type FormEvent } from 'react';
import { apiRequest } from './api';
import { toCampaign, type Campaign, type CampaignApi } from './data';
import Icon from './Icon';

type Props = { onClose: () => void; onCreated: (campaign: Campaign) => void };

export default function CreateModal({ onClose, onCreated }: Props) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError('');
    const data = new FormData(event.currentTarget);
    const payload = {
      name: String(data.get('name') ?? ''), product: String(data.get('product') ?? ''), description: String(data.get('description') ?? ''),
      objective: String(data.get('objective') ?? 'traffic'), location: String(data.get('location') ?? ''), audience: String(data.get('audience') ?? ''),
      budget: Number(data.get('budget')), duration_days: Number(data.get('durationDays')), landing_page: String(data.get('landingPage') ?? ''),
      tone: String(data.get('tone') ?? ''), offer: String(data.get('offer') ?? '') || null, platforms: data.getAll('platforms').map(String),
      brand_guidelines: String(data.get('brandGuidelines') ?? '') || null, existing_copy: String(data.get('existingCopy') ?? '') || null,
      competitor_notes: String(data.get('competitorNotes') ?? '') || null, instructions: String(data.get('instructions') ?? '') || null,
    };
    try { onCreated(toCampaign(await apiRequest<CampaignApi>('/api/v1/campaigns', { method: 'POST', body: JSON.stringify(payload) }))); }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Unable to create this campaign.'); }
    finally { setBusy(false); }
  };
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><section className="modal campaign-modal" role="dialog" aria-modal="true" aria-labelledby="create-title"><div className="modal-header"><div><p className="eyebrow">Campaign brief</p><h2 id="create-title">Create your campaign</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><Icon name="close" /></button></div><p className="modal-copy">Give AdPilot one clear brief. Review every platform version before anything is published.</p>{error && <div className="auth-message error" role="alert">{error}</div>}<form className="brief-form" onSubmit={submit}><div className="form-grid"><label>Campaign name<input required name="name" placeholder="e.g. Summer product launch" /></label><label>Product or service<input required name="product" placeholder="What are you promoting?" /></label><label className="form-wide">Description<textarea required minLength={10} name="description" placeholder="What makes this offer valuable?" /></label><label>Objective<select name="objective"><option value="traffic">Traffic</option><option value="leads">Leads</option><option value="sales">Sales / conversions</option><option value="brand_awareness">Brand awareness</option><option value="engagement">Engagement</option></select></label><label>Target location<input required name="location" placeholder="e.g. United States" /></label><label className="form-wide">Target audience<input required name="audience" placeholder="Who should see this campaign?" /></label><label>Budget (USD)<input required type="number" min="1" step="0.01" name="budget" placeholder="100" /></label><label>Duration (days)<input required type="number" min="1" max="365" defaultValue="30" name="durationDays" /></label><label className="form-wide">Landing page URL<input required type="url" name="landingPage" placeholder="https://example.com/offer" /></label><label>Preferred tone<input required name="tone" defaultValue="Confident" /></label><label>Offer / discount<input name="offer" placeholder="20% off this week" /></label></div><fieldset className="platform-picker"><legend>Desired platforms</legend>{['Meta', 'Google', 'YouTube'].map((platform) => <label className="platform-check" key={platform}><input type="checkbox" name="platforms" value={platform} defaultChecked={platform === 'Meta'} />{platform}</label>)}</fieldset><details className="optional-brief"><summary>Add optional campaign context</summary><div className="form-grid"><label>Brand guidelines<textarea name="brandGuidelines" placeholder="Colors, voice, constraints" /></label><label>Existing copy<textarea name="existingCopy" placeholder="Copy you already use" /></label><label>Competitor notes<textarea name="competitorNotes" placeholder="Relevant references" /></label><label>Additional instructions<textarea name="instructions" placeholder="Anything else AdPilot should know?" /></label></div></details><div className="modal-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancel</button><button className="button button-primary" disabled={busy}>{busy ? 'Saving…' : 'Create campaign'} {!busy && <Icon name="arrow" size={16} />}</button></div></form></section></div>;
}
