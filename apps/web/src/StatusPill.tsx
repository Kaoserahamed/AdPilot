export default function StatusPill({ status }: { status: string }) {
  const label = status === 'DRAFT' ? 'Draft' : status === 'PENDING_REVIEW' ? 'Pending review' : status.charAt(0) + status.slice(1).toLowerCase();
  return <span className={`status-pill status-${label.toLowerCase().replace(' ', '-')}`}><span className="status-dot" />{label}</span>;
}
