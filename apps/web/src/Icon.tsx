import type { ReactNode } from 'react';

type IconProps = { name: string; size?: number };

export default function Icon({ name, size = 18 }: IconProps) {
  const paths: Record<string, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    campaign: <><path d="m3 11 18-5v12L3 13v-2Z" /><path d="M11.6 16.2 13 21H7l-1.2-5.4" /></>,
    library: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z" /><path d="M4 5.5v16M8 7h8M8 11h8" /></>,
    analytics: <><path d="M4 19V5M4 19h17" /><path d="m7 15 3-4 3 2 5-7" /></>,
    platforms: <><circle cx="12" cy="12" r="8.5" /><path d="M3.7 9h16.6M3.7 15h16.6M12 3.5c2.2 2.3 3.2 5.1 3.2 8.5s-1 6.2-3.2 8.5c-2.2-2.3-3.2-5.1-3.2-8.5s1-6.2 3.2-8.5Z" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19 15a2 2 0 0 0 .4 2l-2.5 2.5a2 2 0 0 0-2-.4 2 2 0 0 0-1.1 1.7h-3.6a2 2 0 0 0-1.1-1.7 2 2 0 0 0-2 .4l-2.5-2.5A2 2 0 0 0 5 15a2 2 0 0 0-1.7-1.1h-.1v-3.6A2 2 0 0 0 5 9a2 2 0 0 0 .4-2l2.5-2.5a2 2 0 0 0 2 .4A2 2 0 0 0 11 3.2V3h3.6v.2A2 2 0 0 0 15.7 5a2 2 0 0 0 2-.4l2.5 2.5a2 2 0 0 0-.4 2 2 2 0 0 0 1.7 1.1h.1v3.6h-.1A2 2 0 0 0 19 15Z" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    spark: <><path d="m12 3 1.2 5.8L19 10l-5.8 1.2L12 17l-1.2-5.8L5 10l5.8-1.2L12 3Z" /></>,
    check: <path d="m5 12 4.2 4.2L19 6.5" />,
    upload: <><path d="M12 16V4M7 9l5-5 5 5" /><path d="M5 15v4h14v-4" /></>,
    pause: <><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    chevron: <path d="m7 10 5 5 5-5" />,
    external: <><path d="M14 5h5v5M19 5l-8 8" /><path d="M19 14v4H6V6h4" /></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
