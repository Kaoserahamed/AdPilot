import { useEffect, useState } from 'react';
import { apiRequest, type AuthUser } from './api';
import { activity, formatSpend, formatUpdated, navItems, toCampaign, type Campaign, type CampaignApi } from './data';
import Icon from './Icon';
import Metric from './Metric';
import StatusPill from './StatusPill';
import CreateModal from './CreateModal';
import AuthScreen from './AuthScreen';


function CampaignsTable({ campaigns, onDelete, loading, error }: { campaigns: Campaign[]; onDelete: (id: number) => void; loading: boolean; error: string | null }) {
  return <section className="panel"><div className="panel-header"><div><h2>Recent campaigns</h2><p>Manage and monitor your latest work</p></div><button className="text-button">View all <Icon name="arrow" size={15} /></button></div>{loading ? <div className="table-state">Loading campaigns…</div> : error ? <div className="table-state error-state">{error}</div> : campaigns.length === 0 ? <div className="table-state"><strong>No campaigns yet</strong><span>Create your first brief to get started.</span></div> : <div className="table-wrap"><table><thead><tr><th>Campaign</th><th>Platforms</th><th>Status</th><th>Spend</th><th>Last updated</th><th /></tr></thead><tbody>{campaigns.map((campaign) => <tr key={campaign.id}><td><div className="campaign-name"><i><Icon name="campaign" size={17} /></i><div><strong>{campaign.name}</strong><small>{campaign.product}</small></div></div></td><td><div className="platforms">{campaign.platforms.map((platform) => <span key={platform}>{platform}</span>)}</div></td><td><StatusPill status={campaign.status} /></td><td className="spend">{formatSpend(campaign)}</td><td className="updated">{formatUpdated(campaign.updatedAt)}</td><td><button className="row-menu delete-campaign" onClick={() => onDelete(campaign.id)} aria-label={`Delete ${campaign.name}`}>×</button></td></tr>)}</tbody></table></div>}</section>;
}

function ActivityPanel() {
  return <section className="panel activity-panel"><div className="panel-header"><div><h2>Recent activity</h2><p>Latest changes across your workspace</p></div></div><div className="activity-list">{activity.map(([icon, title, detail, time, tone]) => <div className="activity-item" key={title}><i className={`activity-${tone}`}><Icon name={icon} size={15} /></i><p><strong>{title}</strong><span>{detail}</span><small>{time}</small></p></div>)}</div><button className="activity-link">View activity log <Icon name="arrow" size={14} /></button></section>;
}

function EmptyState({ title }: { title: string }) {
  return <section className="empty-state panel"><div><Icon name="analytics" size={28} /></div><p className="eyebrow">Coming next in your workspace</p><h1>{title}</h1><p>This foundation area will connect to your {title.toLowerCase()} data and workflows in the next feature.</p></section>;
}

function Workspace({ onLogout }: { onLogout: () => void }) {
  const [activeNav, setActiveNav] = useState('Overview');
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignsLoading, setCampaignsLoading] = useState(true);
  const [campaignsError, setCampaignsError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  useEffect(() => {
    apiRequest<CampaignApi[]>('/api/v1/campaigns').then((items) => setCampaigns(items.map(toCampaign))).catch((error: unknown) => setCampaignsError(error instanceof Error ? error.message : 'Unable to load campaigns.')).finally(() => setCampaignsLoading(false));
  }, []);
  const addCampaign = (campaign: Campaign) => { setCampaigns((current) => [campaign, ...current]); setShowCreate(false); setActiveNav('Campaigns'); };
  const removeCampaign = async (id: number) => { await apiRequest(`/api/v1/campaigns/${id}`, { method: 'DELETE' }); setCampaigns((current) => current.filter((campaign) => campaign.id !== id)); };
  const isWorkspace = activeNav === 'Overview' || activeNav === 'Campaigns';
  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}><div className="brand"><div className="brand-mark" /><span>adpilot</span><small>BETA</small></div><div className="workspace-switcher"><b>N</b><div><strong>Northstar Studio</strong><small>Personal workspace</small></div><Icon name="chevron" size={15} /></div><nav><p className="nav-label">Workspace</p>{navItems.map((item) => <button className={`nav-item ${activeNav === item.label ? 'active' : ''}`} key={item.label} onClick={() => { setActiveNav(item.label); setMobileNav(false); }}><Icon name={item.icon} /><span>{item.label}</span>{item.count && <em>{item.count}</em>}</button>)}</nav><div className="sidebar-bottom"><button className="nav-item" onClick={() => setActiveNav('Settings')}><Icon name="settings" /><span>Settings</span></button><div className="help-card"><div className="help-spark"><Icon name="spark" size={16} /></div><strong>Meet your copilot</strong><p>Turn one brief into a campaign for every channel.</p><button onClick={() => setShowCreate(true)}>Try it now <Icon name="arrow" size={14} /></button></div><div className="profile"><b>AM</b><div><strong>Alex Morgan</strong><small>alex@northstar.co</small></div><button className="logout-button" onClick={onLogout}>Log out</button></div></div></aside>




    {mobileNav && <button className="mobile-overlay" onClick={() => setMobileNav(false)} aria-label="Close navigation" />}
    <main className="main-content"><header><button className="mobile-menu" onClick={() => setMobileNav(!mobileNav)} aria-label="Toggle navigation"><Icon name="menu" /></button><div className="breadcrumbs"><span>Workspace</span><b>/</b><strong>{activeNav}</strong></div><div className="topbar-actions"><button className="notification" aria-label="Notifications"><Icon name="campaign" /><i /></button><span className="environment"><i />Sandbox mode</span><button className="button button-primary button-small" onClick={() => setShowCreate(true)}><Icon name="plus" size={16} />New campaign</button></div></header><div className="page-content">
      {isWorkspace ? <><div className="welcome-row"><div><p className="eyebrow">{activeNav === 'Campaigns' ? 'Campaign workspace' : 'Tuesday, March 24, 2026'}</p><h1>{activeNav === 'Campaigns' ? 'Your campaigns' : 'Good morning, Alex'} <span>✦</span></h1><p className="subtitle">{activeNav === 'Campaigns' ? 'Build, review, and publish every campaign from one place.' : 'Here is what is happening across your ad campaigns.'}</p></div><button className="button button-secondary export-button">Export report <Icon name="external" size={16} /></button></div>{activeNav === 'Overview' && <div className="metric-grid"><Metric label="Total spend" value="$1,932.80" change="+18.4%" accent="violet" icon="campaign" /><Metric label="Impressions" value="284,921" change="+24.8%" accent="blue" icon="analytics" /><Metric label="Clicks" value="8,421" change="+11.2%" accent="green" icon="arrow" /><Metric label="Conversions" value="327" change="+8.6%" accent="amber" icon="check" /></div>}<div className="insight"><div><Icon name="spark" size={21} /></div><p><strong>Your campaigns are gaining momentum</strong><span>Spend is up 18.4% this month, while your cost per conversion is down 6.2%.</span></p><button className="text-button">View insights <Icon name="arrow" size={15} /></button></div><div className="content-grid"><CampaignsTable campaigns={campaigns} onDelete={removeCampaign} loading={campaignsLoading} error={campaignsError} /><ActivityPanel /></div></> : <EmptyState title={activeNav} />}
    </div><footer><span>© 2026 AdPilot</span><span>Sandbox workspace · Data refreshes automatically</span><span><a href="#help">Help center</a><a href="#status"><i />All systems operational</a></span></footer></main>{showCreate && <CreateModal onClose={() => setShowCreate(false)} onCreated={addCampaign} />}</div>;
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<AuthUser>('/api/v1/auth/me')
      .then(setUser)
      .catch((error: unknown) => {
        if (!(error instanceof Error) || !error.message.includes('Authentication required')) setApiError(error instanceof Error ? error.message : 'Unable to reach the AdPilot API.');
      })
      .finally(() => setLoading(false));
  }, []);

  const logout = async () => {
    try { await apiRequest('/api/v1/auth/logout', { method: 'POST' }); } finally { setUser(null); }
  };

  if (loading) return <div className="auth-loading"><div className="auth-loading-mark"><span /></div><p>Loading your workspace…</p></div>;
  if (!user) return <AuthScreen onAuthenticated={setUser} apiError={apiError} />;
  return <Workspace onLogout={logout} />;
}
