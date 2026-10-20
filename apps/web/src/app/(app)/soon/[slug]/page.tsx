"use client";

/** The "Coming soon" page for every nav item that isn't built yet (lib/nav `soon`). */

import Link from "next/link";
import { useParams } from "next/navigation";

import { NavIcon } from "@/components/NavIcons";
import { PageHeader } from "@/components/PageHeader";
import { NAV, SOON_COPY, itemsOf } from "@/lib/nav";

export default function ComingSoonPage() {
  const { slug } = useParams<{ slug: string }>();
  const section = NAV.find((s) => itemsOf(s).some((i) => i.soon === slug));
  const item = section && itemsOf(section).find((i) => i.soon === slug);
  const title = item?.label ?? "Coming soon";

  return (
    <>
      <PageHeader
        eyebrow={section?.label ?? ""}
        breadcrumb={section?.label ?? ""}
        title={title}
        meta={<span className="soon-tag soon-tag-lg">Under development</span>}
      />
      <div className="page-content">
        <div className="card soon-card">
          <span className="soon-icon" aria-hidden>
            <NavIcon name={item?.icon ?? "hammer"} size={26} />
          </span>
          <h2 className="t-card-title">{title} is coming soon</h2>
          <p className="t-description">{SOON_COPY[slug] ?? "This part of The Hub Zone is still being built."}</p>
          <p className="t-caption">It&apos;s on the roadmap. Want it sooner, or have ideas for it? Tell us with Send Feedback under Help.</p>
          <Link href="/projects" className="btn btn-secondary" style={{ width: "fit-content" }}>
            Back to projects
          </Link>
        </div>
      </div>
    </>
  );
}
