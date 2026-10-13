"use client";

import { TableDocumentPage } from "@/components/project/TableDocument";
import { REQUIREMENTS_DOCUMENT } from "@/lib/documents";

export default function RequirementsPage() {
  return <TableDocumentPage def={REQUIREMENTS_DOCUMENT} />;
}
