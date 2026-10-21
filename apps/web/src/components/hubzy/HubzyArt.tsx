/**
 * Hubzy, the mascot — the SVG from The Hub Zone mockup (rounded indigo body,
 * red antenna bulb, glossy eyes, blush, two swaying arms, ground shadow),
 * split into groups the idle behaviour can move: the eyes (blink, glance),
 * the mouth (smile, talk), the antenna (wiggle) and the whole body (hop, tilt).
 */

import type { CSSProperties } from "react";

import type { HubzyExpression } from "./config";

export type HubzyFace = {
  blinking: boolean;
  /** Where the pupils look, in SVG units (about ±3.5 x, ±2.5 y). */
  look: { x: number; y: number };
  expression: HubzyExpression | null;
  talking?: boolean;
};

// Gradient ids are prefixed so a second Hubzy (the chat header later) can't clash.
export function HubzyArt({ face, idPrefix = "hz" }: { face: HubzyFace; idPrefix?: string }) {
  const body = `${idPrefix}-body`;
  const bulb = `${idPrefix}-bulb`;
  const ball = `${idPrefix}-ball`;
  const eyesStyle = { "--hz-look-x": `${face.look.x}px`, "--hz-look-y": `${face.look.y}px` } as CSSProperties;
  return (
    <svg className="hubzy-svg" viewBox="0 0 160 195" aria-hidden="true" data-expression={face.expression ?? undefined} data-talking={face.talking || undefined}>
      <defs>
        <radialGradient id={body} cx="38%" cy="30%" r="78%">
          <stop offset="0" stopColor="#7E77F3" />
          <stop offset="55%" stopColor="#5B53E8" />
          <stop offset="100%" stopColor="#453CD1" />
        </radialGradient>
        <radialGradient id={bulb} cx="38%" cy="30%" r="72%">
          <stop offset="0" stopColor="#FF8181" />
          <stop offset="100%" stopColor="#DE3B41" />
        </radialGradient>
        <radialGradient id={ball} cx="38%" cy="30%" r="78%">
          <stop offset="0" stopColor="#726AEF" />
          <stop offset="100%" stopColor="#453CD1" />
        </radialGradient>
      </defs>
      <ellipse className="hubzy-sh" cx="80" cy="185" rx="42" ry="7" fill="#191B2E" opacity=".45" />
      <g className="hubzy-hop">
        <g className="hubzy-float">
          <g className="hubzy-antenna">
            <line x1="80" y1="41" x2="80" y2="20" stroke="#1A1B2E" strokeWidth="4" strokeLinecap="round" />
            <circle className="hubzy-bulb" cx="80" cy="15" r="11" fill={`url(#${bulb})`} stroke="#1A1B2E" strokeWidth="3" />
            <path d="M75 11a6 6 0 0 1 5-4" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" fill="none" opacity=".85" />
          </g>
          <g className="hubzy-arm-l">
            <line x1="34" y1="120" x2="23" y2="152" stroke="#1A1B2E" strokeWidth="5" strokeLinecap="round" />
            <circle cx="22" cy="159" r="11" fill={`url(#${ball})`} stroke="#1A1B2E" strokeWidth="3" />
            <path d="M16 156a7 7 0 0 1 5-4" stroke="#fff" strokeWidth="2" strokeLinecap="round" fill="none" opacity=".7" />
          </g>
          <g className="hubzy-arm-r">
            <line x1="126" y1="120" x2="137" y2="152" stroke="#1A1B2E" strokeWidth="5" strokeLinecap="round" />
            <circle cx="138" cy="159" r="11" fill={`url(#${ball})`} stroke="#1A1B2E" strokeWidth="3" />
            <path d="M132 156a7 7 0 0 1 5-4" stroke="#fff" strokeWidth="2" strokeLinecap="round" fill="none" opacity=".7" />
          </g>
          <g className="hubzy-head">
            <circle cx="80" cy="98" r="58" fill={`url(#${body})`} stroke="#1A1B2E" strokeWidth="4" />
            {/* rim light */}
            <path d="M116 64a58 58 0 0 1 12 42" stroke="#C7CCFF" strokeWidth="4" strokeLinecap="round" fill="none" opacity=".55" />
            <ellipse className="hubzy-blush" cx="54" cy="109" rx="10" ry="5" fill="#FF9DC0" opacity=".82" />
            <ellipse className="hubzy-blush" cx="106" cy="109" rx="10" ry="5" fill="#FF9DC0" opacity=".82" />
            <g className="hubzy-eyes" style={eyesStyle} data-blink={face.blinking || undefined}>
              <g className="hubzy-eye">
                <circle cx="63" cy="95" r="7.5" fill="#15162A" />
                <circle cx="60.8" cy="92.4" r="2.3" fill="#fff" />
              </g>
              <g className="hubzy-eye">
                <circle cx="97" cy="95" r="7.5" fill="#15162A" />
                <circle cx="94.8" cy="92.4" r="2.3" fill="#fff" />
              </g>
            </g>
            <path className="hubzy-mouth" d="M71 116q9 8 18 0" stroke="#15162A" strokeWidth="3.2" strokeLinecap="round" fill="none" />
          </g>
        </g>
      </g>
    </svg>
  );
}
