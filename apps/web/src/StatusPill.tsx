import type { CampaignStatus } from './data';

export default function StatusPill({ status }: { status: CampaignStatus }) {
  return <span className={`status-pill status-${status.toLowerCase().replace(' ', '-')}`}><span className="status-dot" />{status}</span>;
}
