"use client";

/** A workspace tool page (lib/tools): a tracker, or one of the read-only data pages. */

import { useParams } from "next/navigation";

import { PageHeader } from "@/components/PageHeader";
import { ImplementationDashboard } from "@/components/tools/ImplementationDashboard";
import { DataMigration } from "@/components/tools/DataMigration";
import { DataDocumentationTool, DatabaseTool } from "@/components/tools/PortalData";
import { TrackerTool } from "@/components/tools/TrackerTool";
import { Callout } from "@/components/ui";
import { useAppSession } from "@/components/AppSession";
import { toolBySlug } from "@/lib/tools";

export default function ToolPage() {
  const { slug } = useParams<{ slug: string }>();
  const { me } = useAppSession();
  const tool = toolBySlug(slug);

  if (!tool) {
    return (
      <div className="page-content">
        <Callout tone="error" title="There's no page here">
          Pick a page from the rail on the left.
        </Callout>
      </div>
    );
  }
  return (
    <>
      <PageHeader
        eyebrow={`${tool.section.toUpperCase()} / ${tool.title.toUpperCase()}`}
        breadcrumb={`${me.workspace_name}  /  ${tool.section}`}
        title={tool.title}
        description={tool.description}
      />
      <div className="page-content">
        {tool.dataPage === "implementation-dashboard" ? (
          <ImplementationDashboard />
        ) : tool.dataPage === "database" ? (
          <DatabaseTool />
        ) : tool.dataPage === "data-documentation" ? (
          <DataDocumentationTool />
        ) : tool.dataPage === "data-migration" ? (
          <DataMigration />
        ) : (
          <TrackerTool key={tool.slug} tool={tool} />
        )}
      </div>
    </>
  );
}
