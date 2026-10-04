import { useCallback, useEffect, useState } from 'react';
import { apiRequest } from './api';
import type { Campaign, CampaignStatusResult, PublishResponse, PublishingJob } from './data';
import Icon from './Icon';
import StatusPill from './StatusPill';

type Props = { campaigns: Campaign[]; onPublished: () => void };

const POLL_INTERVAL_MS = 4000;

export default function Publishing({ campaigns, onPublished }: Props) {
  const publishable = campaigns.filter((campaign) => ['READY', 'FAILED', 'PAUSED', 'VALIDATION_FAILED'].includes(campaign.status));
  const [campaignId, setCampaignId] = useState(publishable[0]?.id ?? campaigns[0]?.id ?? 0);
  const [status, setStatus] = useState<CampaignStatusResult | null>(null);
  const [jobs, setJobs] = useState<PublishingJob[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadStatus = useCallback(async (id: number) => {
    if (!id) return;
    try {
      setStatus(await apiRequest<CampaignStatusResult>(`/api/v1/campaigns/${id}/status`));
    } catch {
      setStatus(null);
    }
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      setJobs(await apiRequest<PublishingJob[]>('/api/v1/publishing/jobs'));
    } catch {
      setJobs([]);
    }
  }, []);

  useEffect(() => { void loadJobs(); }, [loadJobs]);
  useEffect(() => { void loadStatus(campaignId); }, [campaignId, loadStatus]);

  const inFlight = status?.jobs.some((job) => job.status === 'QUEUED' || job.status === 'RUNNING') ?? false;
  useEffect(() => {
    if (!inFlight) return undefined;
    const timer = setInterval(() => { void loadStatus(campaignId); void loadJobs(); }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [inFlight, campaignId, loadStatus, loadJobs]);

  const publish = async () => {
    if (!campaignId) return;
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await apiRequest<PublishResponse>(`/api/v1/campaigns/${campaignId}/publish`, { method: 'POST' });
      setNotice(result.message);
      await Promise.all([loadStatus(campaignId), loadJobs()]);
      onPublished();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Publishing failed.');
    } finally { setBusy(false); }
  };

  const pause = async () => {
    if (!campaignId) return;
    setBusy(true); setError(''); setNotice('');
    try {
      setStatus(await apiRequest<CampaignStatusResult>(`/api/v1/campaigns/${campaignId}/pause`, { method: 'POST' }));
      await loadJobs();
      onPublished();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Pausing failed.');
    } finally { setBusy(false); }
  };

  const retry = async (jobId: number) => {
    setBusy(true); setError('');
    try {
      await apiRequest<PublishingJob>(`/api/v1/publishing/jobs/${jobId}/retry`, { method: 'POST' });
      await Promise.all([loadStatus(campaignId), loadJobs()]);
      onPublished();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Retry failed.');
    } finally { setBusy(false); }
  };

  const canPublish = Boolean(campaignId) && !inFlight && !busy;
  const canPause = Boolean(status?.platforms.length) && !busy;
return <section className="publish-page">
    <div className="review-header">
      <div><p className="eyebrow">Publishing workflow</p><h1>Submit campaigns to platforms</h1><p className="subtitle">Publishing runs in the background. You stay in control of every submission.</p></div>
      <span className="review-badge"><Icon name="check" size={15} />Review required first</span>
    </div>

    <div className="review-toolbar">
      <label>Campaign
        <select value={campaignId} onChange={(event) => { setCampaignId(Number(event.target.value)); setNotice(''); setError(''); }}>
          <option value={0}>Select a campaign</option>
          {campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name} · {campaign.status}</option>)}
        </select>
      </label>
      <button className="button button-primary" disabled={!canPublish} onClick={publish}>{busy ? 'Working…' : 'Publish campaign'} {!busy && <Icon name="arrow" size={15} />}</button>
      <button className="button button-secondary" disabled={!canPause} onClick={pause}>Pause</button>
    </div>

    {error && <div className="auth-message error" role="alert">{error}</div>}
    {notice && <div className="auth-message success" role="status">{notice}</div>}

    {status && <div className="panel">
      <div className="panel-header"><div><h2>Submission status</h2><p>Current state for this campaign</p></div><StatusPill status={status.status} /></div>
      {status.platforms.length === 0
        ? <div className="table-state"><strong>Not submitted yet</strong><span>This campaign has not been sent to any advertising platform.</span></div>
        : <div className="table-wrap"><table><thead><tr><th>Platform</th><th>External campaign</th><th>Status</th><th>Detail</th></tr></thead><tbody>
            {status.platforms.map((item) => <tr key={item.id}><td><strong>{item.platform}</strong></td><td className="mono">{item.external_campaign_id}</td><td><StatusPill status={item.status} /></td><td>{item.detail ?? '—'}</td></tr>)}
          </tbody></table></div>}
    </div>}

    <div className="panel">
      <div className="panel-header"><div><h2>Publishing jobs</h2><p>Every submission is tracked and retryable</p></div></div>
      {jobs.length === 0
        ? <div className="table-state"><strong>No publishing jobs yet</strong><span>Jobs appear here as soon as you publish a campaign.</span></div>
        : <div className="table-wrap"><table><thead><tr><th>Job</th><th>Campaign</th><th>Status</th><th>Attempt</th><th>Error</th><th /></tr></thead><tbody>
            {jobs.map((job) => <tr key={job.id}>
              <td className="mono">#{job.id}</td>
              <td>{campaigns.find((campaign) => campaign.id === job.campaign_id)?.name ?? `Campaign ${job.campaign_id}`}</td>
              <td><StatusPill status={job.status} /></td>
              <td>{job.attempt}</td>
              <td>{job.error ?? '—'}</td>
              <td>{job.status === 'FAILED' && job.attempt < 3 && <button className="text-button" disabled={busy} onClick={() => retry(job.id)}>Retry</button>}</td>
            </tr>)}
          </tbody></table></div>}
    </div>
  </section>;
}