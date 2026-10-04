import { useCallback, useEffect, useState } from 'react';
import { apiRequest } from './api';
import {
  DERIVED_METRIC_LABELS,
  formatCurrency,
  formatMetric,
  formatNullable,
  type AnalysisAnswer,
  type AnalyticsOverview,
  type Campaign,
} from './data';
import Icon from './Icon';

type Props = { campaigns: Campaign[] };

function SourceTag({ source, calculated }: { source: string; calculated: boolean }) {
  return <span className={`source-tag ${calculated ? 'source-calculated' : 'source-reported'}`}>{calculated ? 'AdPilot' : source}</span>;
}

export default function AnalyticsDashboard({ campaigns }: Props) {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [campaignId, setCampaignId] = useState(0);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<AnalysisAnswer | null>(null);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState('');

  const load = useCallback(async () => {
    try {
      setOverview(await apiRequest<AnalyticsOverview>('/api/v1/analytics/overview'));
      setError('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load analytics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const syncable = campaigns.filter((campaign) => ['PENDING_REVIEW', 'ACTIVE', 'PAUSED', 'FAILED'].includes(campaign.status));
  useEffect(() => { if (!campaignId && syncable[0]) setCampaignId(syncable[0].id); }, [campaignId, syncable]);

  const sync = async () => {
    if (!campaignId) return;
    setSyncing(true); setError('');
    try {
      await apiRequest(`/api/v1/analytics/campaigns/${campaignId}/sync`, { method: 'POST' });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Metric sync failed.');
    } finally { setSyncing(false); }
  };

  const ask = async () => {
    if (!campaignId) return;
    setAsking(true); setAskError('');
    try {
      setAnswer(await apiRequest<AnalysisAnswer>('/api/v1/ai/analyze', {
        method: 'POST',
        body: JSON.stringify({ campaign_id: campaignId, question: question.trim() || undefined }),
      }));
    } catch (caught) {
      setAskError(caught instanceof Error ? caught.message : 'Unable to answer that question.');
      setAnswer(null);
    } finally { setAsking(false); }
  };

if (loading) return <section className="panel"><div className="table-state">Loading analytics…</div></section>;

  return <section className="analytics-page">
    <div className="review-header">
      <div><p className="eyebrow">Unified analytics</p><h1>Performance across platforms</h1><p className="subtitle">Reported platform metrics are shown separately from values AdPilot derives.</p></div>
      <span className="review-badge"><Icon name="analytics" size={15} />Last {overview?.reporting_period_days ?? 7} days</span>
    </div>

    {error && <div className="auth-message error" role="alert">{error}</div>}

    <div className="review-toolbar">
      <label>Campaign
        <select value={campaignId} onChange={(event) => { setCampaignId(Number(event.target.value)); setAnswer(null); }}>
          <option value={0}>Select a campaign</option>
          {campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}
        </select>
      </label>
      <button className="button button-secondary" disabled={!campaignId || syncing} onClick={sync}>{syncing ? 'Syncing…' : 'Sync metrics'}</button>
    </div>

    {!overview || overview.campaigns.length === 0
      ? <div className="panel"><div className="table-state"><strong>No synced metrics yet</strong><span>Publish a campaign and sync metrics to populate this dashboard.</span></div></div>
      : <>
        <div className="metric-grid">
          <div className="metric-card"><span>Total spend</span><strong>{formatCurrency(overview.total_spend, overview.currency)}</strong><small>Reported by platform</small></div>
          <div className="metric-card"><span>Impressions</span><strong>{formatMetric('impressions', overview.total_impressions)}</strong><small>Reported by platform</small></div>
          <div className="metric-card"><span>Clicks</span><strong>{formatMetric('clicks', overview.total_clicks)}</strong><small>Reported by platform</small></div>
          <div className="metric-card"><span>Conversions</span><strong>{formatMetric('conversions', overview.total_conversions)}</strong><small>Reported by platform</small></div>
        </div>

        <div className="panel">
          <div className="panel-header"><div><h2>Platform breakdown</h2><p>Metrics marked AdPilot are calculated from reported values</p></div></div>
          <div className="table-wrap"><table><thead><tr><th>Platform</th><th>Spend</th><th>Impressions</th><th>Clicks</th><th>Conversions</th><th>CTR</th><th>CPC</th><th>CPA</th><th>ROAS</th></tr></thead><tbody>
            {overview.platforms.map((item) => <tr key={item.platform}>
              <td><strong>{item.platform}</strong></td>
              <td>{formatCurrency(item.spend, item.currency)}</td>
              <td>{formatMetric('impressions', item.impressions)}</td>
              <td>{formatMetric('clicks', item.clicks)}</td>
              <td>{formatMetric('conversions', item.conversions)}</td>
              {(['ctr', 'cpc', 'cpa', 'roas'] as const).map((metric) => <td key={metric}>
                <span className="metric-value">{formatNullable(item[metric])}</span>
                {item.calculated_fields.includes(metric) && <SourceTag source="adpilot" calculated />}
              </td>)}
            </tr>)}
          </tbody></table></div>
        </div>

        <div className="panel">
          <div className="panel-header"><div><h2>Ask AI about performance</h2><p>Answers are grounded in stored metrics only</p></div></div>
          <div className="review-toolbar">
            <label>Question<input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Summarize this campaign." /></label>
            <button className="button button-primary" disabled={!campaignId || asking} onClick={ask}>{asking ? 'Thinking…' : 'Ask AI'}</button>
          </div>
          {askError && <div className="auth-message error" role="alert">{askError}</div>}
          {answer && <div className="analysis-result">
            <div className="analysis-meta">
              <span>Reporting period {answer.period_start.slice(0, 10)} → {answer.period_end.slice(0, 10)}</span>
              <SourceTag source={answer.provider} calculated={false} />
              {!answer.data_complete && <span className="source-tag source-calculated">Incomplete data</span>}
            </div>
            <p className="analysis-summary">{answer.summary}</p>
            <ul className="analysis-highlights">{answer.highlights.map((line) => <li key={line}>{line}</li>)}</ul>
            {!answer.data_complete && <p className="analysis-note">Not reported by any platform: {answer.unavailable.join(', ')}.</p>}
            <details><summary>Metric facts used</summary>
              <ul className="analysis-facts">{answer.facts.map((fact) => <li key={fact.metric}>
                <span>{DERIVED_METRIC_LABELS[fact.metric] ?? fact.metric}</span>
                <strong>{fact.metric === 'spend' ? formatCurrency(fact.value, fact.currency) : formatMetric(fact.metric, fact.value)}</strong>
                <SourceTag source={fact.source} calculated={fact.calculated} />
              </li>)}</ul>
            </details>
          </div>}
        </div>
      </>}
  </section>;
}