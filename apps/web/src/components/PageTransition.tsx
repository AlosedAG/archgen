"use client";

/**
 * Animates the page area when the route changes: the new page fades in with
 * a slight rise instead of hard-cutting. It replays the entrance on the same
 * element (no remount), so page and layout state are never thrown away, and
 * the sidebar and top bar outside it stay still. Reduced motion: a short
 * opacity fade only.
 */

import { motion, useAnimationControls, useReducedMotion } from "framer-motion";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { pageEnter, reduced } from "@/lib/motion";

export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const reduce = useReducedMotion();
  const controls = useAnimationControls();

  useEffect(() => {
    controls.set("hidden");
    void controls.start("visible");
  }, [pathname, controls]);

  return (
    <motion.div className="page-transition" variants={reduce ? reduced.pageEnter : pageEnter} initial="hidden" animate={controls}>
      {children}
    </motion.div>
  );
}
