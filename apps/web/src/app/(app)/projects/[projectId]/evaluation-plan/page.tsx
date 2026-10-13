"use client";

import { TableDocumentPage } from "@/components/project/TableDocument";
import { JOINT_EVALUATION_PLAN } from "@/lib/documents";

export default function EvaluationPlanPage() {
  return <TableDocumentPage def={JOINT_EVALUATION_PLAN} />;
}
