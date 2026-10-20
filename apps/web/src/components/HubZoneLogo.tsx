import { useId } from "react";

/** The Hub Zone mark: an indigo hexagon holding a hub-and-spoke graph (one coral node). */
export function HubZoneLogo({ size = 34, className }: { size?: number; className?: string }) {
  const gradient = useId();
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 32 32" aria-hidden focusable="false">
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6E66EC" />
          <stop offset="1" stopColor="#453CD1" />
        </linearGradient>
      </defs>
      <path d="M16 2.3 27 8.6 V20.4 L16 26.7 L5 20.4 V8.6 Z" fill={`url(#${gradient})`} />
      <g stroke="#fff" strokeOpacity=".9" strokeWidth="1.3" strokeLinecap="round">
        <line x1="16" y1="14.6" x2="16" y2="8.8" />
        <line x1="16" y1="14.6" x2="10.2" y2="19.4" />
        <line x1="16" y1="14.6" x2="21.8" y2="19.4" />
      </g>
      <circle cx="16" cy="14.6" r="2.5" fill="#fff" />
      <circle cx="16" cy="8.4" r="2" fill="#FF6B4A" />
      <circle cx="10" cy="19.7" r="2" fill="#fff" />
      <circle cx="22" cy="19.7" r="2" fill="#fff" />
    </svg>
  );
}

/** Logo + "The Hub Zone" wordmark ("Zone" in indigo). */
export function HubZoneBrand({ size = 34 }: { size?: number }) {
  return (
    <span className="brand">
      <HubZoneLogo size={size} className="brand-logo" />
      <span className="brand-wordmark">
        The Hub <span className="brand-zone">Zone</span>
      </span>
    </span>
  );
}
