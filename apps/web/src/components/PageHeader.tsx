"use client";

import { motion } from "framer-motion";

/** The full-bleed purple banner every page opens with: step eyebrow, breadcrumb, title, description. */
export function PageHeader({
  eyebrow,
  breadcrumb,
  title,
  description,
}: {
  eyebrow: string;
  breadcrumb: string;
  title: string;
  description: string;
}) {
  return (
    <header className="page-header">
      <div className="page-header-context">
        <span className="page-header-eyebrow">{eyebrow}</span>
        <motion.span key={breadcrumb} className="page-header-breadcrumb" initial={{ opacity: 0.4 }} animate={{ opacity: 1 }}>
          {breadcrumb}
        </motion.span>
      </div>
      <motion.h1 initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        {title}
      </motion.h1>
      <p className="page-header-description">{description}</p>
    </header>
  );
}
