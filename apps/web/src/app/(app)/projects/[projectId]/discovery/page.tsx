"use client";

import { useAppSession } from "@/components/AppSession";
import { DiscoveryWorkspace } from "@/components/discovery/DiscoveryWorkspace";

export default function DiscoveryPage() {
  const { project } = useAppSession();
  // The project layout only renders this once the project has loaded.
  return project ? <DiscoveryWorkspace key={project.id} project={project} /> : null;
}
