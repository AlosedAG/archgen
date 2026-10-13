"use client";

import { MotionConfig } from "framer-motion";

/** App-wide client providers. Motion respects the OS "reduce motion" setting. */
export function Providers({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
