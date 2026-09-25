import Icon from './Icon';

type Props = { label: string; value: string; change: string; accent: string; icon: string };

export default function Metric({ label, value, change, accent, icon }: Props) {
  return <article className={`metric-card accent-${accent}`}><div className="metric-top"><span>{label}</span><span className="metric-icon"><Icon name={icon} size={17} /></span></div><strong>{value}</strong><small><b>{change}</b> vs. last 30 days</small></article>;
}
