"use client";

/** A row of headline numbers (animated when numeric). */

import { AnimatedNumber } from "../ui";

export function Stats({ items }: { items: [label: string, value: number | string][] }) {
  return (
    <div className="stats">
      {items.map(([label, value]) => (
        <div key={label} className="stat">
          <span className="stat-label">{label}</span>
          <span className="stat-value">{typeof value === "number" ? <AnimatedNumber value={value} /> : value}</span>
        </div>
      ))}
    </div>
  );
}
