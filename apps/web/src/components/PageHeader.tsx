"use client";

/** "STEP 1 / DISCOVER" -> "Step 1 · Discover"; other eyebrows get no step chip. */
function stepLabel(eyebrow: string): string | null {
  const m = /^STEP\s+(\d+)\s*\/\s*(.+)$/i.exec(eyebrow.trim());
  if (!m) return null;
  const name = m[2]!.toLowerCase();
  return `Step ${m[1]} · ${name.charAt(0).toUpperCase()}${name.slice(1)}`;
}

/**
 * Every page's header: the title with its context line and status chips on
 * the right. (The top bar with breadcrumb and search is in the app layout.)
 */
export function PageHeader({
  eyebrow,
  breadcrumb,
  title,
  description,
  meta,
}: {
  eyebrow: string;
  /** The context line under the title, e.g. "Bright Smiles  /  SonaMation". */
  breadcrumb: string;
  title: string;
  description?: string;
  /** Status chips for the right of the title; defaults to the step chip. */
  meta?: React.ReactNode;
}) {
  const step = stepLabel(eyebrow);
  return (
    <header className="page-header">
      <div className="page-header-main">
        <div className="page-header-title">
          <h1>{title}</h1>
          <p className="page-header-context">{breadcrumb.replace(/\s+\/\s+/g, " / ")}</p>
          {description && <p className="page-header-description">{description}</p>}
        </div>
        <div className="page-header-meta">{meta ?? (step && <span className="status-chip status-chip-success">{step}</span>)}</div>
      </div>
    </header>
  );
}
