/**
 * The structured documents rendered by TableDocumentPage: their fields,
 * tables, columns, starting rows and export layout — matching the
 * Streamlit pages they replace (same sections, columns and options).
 */

import { cleanRows, type Column } from "@/components/project/EditableTable";
import type { DocumentDef } from "@/components/project/TableDocument";

const STATUS = ["Not Started", "In Progress", "Complete", "Blocked"];

const goals: Column[] = [{ key: "goal", label: "Goal", placeholder: "e.g. Respond to every enquiry within 4 hours" }];
const requirements: Column[] = [{ key: "requirement", label: "Requirement", kind: "textarea" }];
const definitions: Column[] = [
  { key: "term", label: "Term", width: "220px" },
  { key: "definition", label: "Definition", kind: "textarea" },
];
const risks: Column[] = [
  { key: "type", label: "Type", kind: "select", options: ["Risk", "Challenge"], width: "150px" },
  { key: "description", label: "Description", kind: "textarea" },
];
const plan: Column[] = [
  { key: "milestone", label: "Milestone" },
  { key: "related_requirement", label: "Related Requirement" },
  { key: "target_date", label: "Target Date", kind: "date", width: "160px" },
  { key: "status", label: "Status", kind: "select", options: STATUS, width: "150px" },
];
const questions: Column[] = [{ key: "question", label: "Question", kind: "textarea" }];
const appendix: Column[] = [
  { key: "resource_type", label: "Resource Type", width: "200px" },
  { key: "link_notes", label: "Link / Notes" },
];

export const REQUIREMENTS_DOCUMENT: DocumentDef = {
  module: "requirements",
  title: "Requirements Document",
  eyebrow: "STEP 1 / DISCOVER",
  description:
    "Document the project's purpose, requirements, terminology, risks, plan and open questions — the same structure as HubSpot's WRD template.",
  documentType: "Written Requirements Document",
  fileSuffix: "WRD",
  subtitle: "Documents the customer's business objectives for this HubSpot implementation.",
  blocks: [
    { kind: "heading", title: "Project Overview" },
    { kind: "field", key: "purpose", label: "Purpose", multiline: true, help: "Summarize the purpose of the solutions development." },
    { kind: "table", key: "goals", title: "Goals", columns: goals, defaults: 2, addLabel: "+ Add goal" },
    {
      kind: "table",
      key: "requirements",
      title: "Customer Requirements",
      caption: "The functionality to be developed. Numbered order matters — the Test Case Document can load these as its starting point.",
      columns: requirements,
      defaults: 3,
      addLabel: "+ Add requirement",
    },
    {
      kind: "table",
      key: "definitions",
      title: "Project Definitions",
      caption: "Terms based on the specific language the customer uses.",
      columns: definitions,
      defaults: 2,
      required: ["term"],
    },
    {
      kind: "table",
      key: "risks",
      title: "Known Challenges or Risks",
      columns: risks,
      defaults: [{ type: "Risk" }, { type: "Challenge" }],
      required: ["description"],
    },
    {
      kind: "table",
      key: "plan",
      title: "Project Plan",
      caption: "A draft for the execution team — not a commitment.",
      columns: plan,
      defaults: 2,
      required: ["milestone"],
    },
    { kind: "table", key: "questions", title: "Open Questions", columns: questions, defaults: 2, addLabel: "+ Add question" },
    {
      kind: "table",
      key: "appendix",
      title: "Appendix and Resources",
      caption: "Citations, integration details, specifications, object field maps, APIs, and diagram links.",
      columns: appendix,
      defaults: ["Citation", "Integration", "Specification", "Object field map", "API", "ERD"].map((t) => ({ resource_type: t })),
      required: ["link_notes"],
    },
  ],
  exportSections: (s) => [
    ["Project Overview", s.fields.purpose ? [{ Field: "Purpose", Value: s.fields.purpose }] : []],
    ["Goals", cleanRows(goals, s.tables.goals ?? [])],
    ["Customer Requirements", cleanRows(requirements, s.tables.requirements ?? [])],
    ["Project Definitions", cleanRows(definitions, s.tables.definitions ?? [], ["term"])],
    ["Known Challenges or Risks", cleanRows(risks, s.tables.risks ?? [], ["description"])],
    ["Project Plan", cleanRows(plan, s.tables.plan ?? [], ["milestone"])],
    ["Open Questions", cleanRows(questions, s.tables.questions ?? [])],
    ["Appendix and Resources", cleanRows(appendix, s.tables.appendix ?? [], ["link_notes"])],
  ].map(([title, rows]) => ({ title: title as string, rows: rows as Record<string, string>[] })),
};

const milestones: Column[] = [
  { key: "target_date", label: "Target Date", kind: "date", width: "150px" },
  { key: "status", label: "Status", kind: "select", options: STATUS, width: "140px" },
  { key: "milestone", label: "Milestone" },
  { key: "link", label: "Link / Recording" },
  { key: "prospect_contact", label: "Prospect Contact" },
  { key: "owner", label: "Owner (Solutions Partner)" },
  { key: "outcome", label: "Outcome / Notes", kind: "textarea" },
];
const team: Column[] = [
  { key: "side", label: "Side", kind: "select", options: ["Prospect", "Solutions Partner"], width: "170px" },
  { key: "role", label: "Role" },
  { key: "member", label: "Team Member" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone", width: "140px" },
  { key: "country", label: "Country", width: "130px" },
];
const needs: Column[] = [
  { key: "functionality", label: "Functionality" },
  { key: "confirmed", label: "Confirmed", kind: "checkbox", width: "100px" },
  { key: "notes", label: "Notes / Links", kind: "textarea" },
];
const jepQuestions: Column[] = [
  { key: "question", label: "Question", kind: "textarea" },
  { key: "contact", label: "Contact", width: "200px" },
  { key: "notes", label: "Notes / Links" },
];

export const JOINT_EVALUATION_PLAN: DocumentDef = {
  module: "evaluation_plan",
  title: "Joint Evaluation Plan",
  eyebrow: "STEP 1 / DISCOVER",
  description:
    "What needs to happen, when, and who's involved at each stage of the evaluation — milestones, team, technical and business needs, and open questions.",
  documentType: "Joint Evaluation Plan",
  fileSuffix: "JEP",
  subtitle: "A mutually agreed set of steps for this evaluation: what needs to happen, when, and who's involved.",
  blocks: [
    { kind: "heading", title: "Solutions partner contact" },
    { kind: "field", key: "contact_name", label: "Contact name" },
    { kind: "field", key: "contact_phone", label: "Contact phone" },
    { kind: "field", key: "contact_email", label: "Contact email" },
    {
      kind: "table",
      key: "milestones",
      title: "Milestones",
      caption: "What needs to happen, when, and who's involved — the running record of the evaluation.",
      columns: milestones,
      defaults: 3,
      required: ["milestone"],
      addLabel: "+ Add milestone",
    },
    {
      kind: "table",
      key: "team",
      title: "Team Members",
      columns: team,
      defaults: [{ side: "Prospect" }, { side: "Solutions Partner" }],
      required: ["member"],
      addLabel: "+ Add team member",
    },
    { kind: "table", key: "technical", title: "Technical Needs", columns: needs, defaults: 3, required: ["functionality"] },
    { kind: "table", key: "business", title: "Business Needs", columns: needs, defaults: 2, required: ["functionality"] },
    { kind: "table", key: "questions", title: "Questions", columns: jepQuestions, defaults: 2, required: ["question"] },
  ],
  exportSections: (s) => [
    {
      title: "Solutions Partner Contact",
      rows: [
        { Field: "Contact Name", Value: s.fields.contact_name ?? "" },
        { Field: "Contact Phone", Value: s.fields.contact_phone ?? "" },
        { Field: "Contact Email", Value: s.fields.contact_email ?? "" },
      ].filter((r) => r.Value.trim()),
    },
    { title: "Milestones", rows: cleanRows(milestones, s.tables.milestones ?? [], ["milestone"]) },
    { title: "Team Members", rows: cleanRows(team, s.tables.team ?? [], ["member"]) },
    { title: "Technical Needs", rows: cleanRows(needs, s.tables.technical ?? [], ["functionality"]) },
    { title: "Business Needs", rows: cleanRows(needs, s.tables.business ?? [], ["functionality"]) },
    { title: "Questions", rows: cleanRows(jepQuestions, s.tables.questions ?? [], ["question"]) },
  ],
};

export const TEST_CASE_COLUMNS: Column[] = [
  { key: "requirement", label: "Requirement", width: "220px" },
  { key: "description", label: "Test Case Description", kind: "textarea", width: "260px" },
  { key: "steps", label: "Steps to Test", kind: "textarea", width: "260px" },
  { key: "expected", label: "Expected Result", kind: "textarea", width: "200px" },
  { key: "round", label: "Round", kind: "select", options: ["QA", "UAT"], width: "100px" },
  { key: "actual", label: "Actual Result", kind: "select", options: ["Not Tested", "Met Expectations", "Issues Identified"], width: "170px" },
  { key: "details", label: "Actual Result Details", kind: "textarea", width: "220px" },
  { key: "feedback", label: "Feedback / Notes", kind: "textarea", width: "200px" },
];

export const TEST_CASE_DOCUMENT: DocumentDef = {
  module: "test_cases",
  title: "Test Case Document",
  eyebrow: "STEP 5 / DELIVER & TEST",
  description: "One row per test case, covering both testing rounds: internal QA first, then customer UAT.",
  documentType: "Test Case Document",
  fileSuffix: "test_cases",
  subtitle: "QA and UAT test cases for this HubSpot build, one row per requirement tested.",
  blocks: [
    {
      kind: "table",
      key: "cases",
      title: "Test Cases",
      caption: "Use the Round column to tell QA and UAT apart.",
      columns: TEST_CASE_COLUMNS,
      defaults: 3,
      required: ["requirement", "description"],
      addLabel: "+ Add test case",
    },
  ],
  exportSections: (s) => [{ title: "Test Cases", rows: cleanRows(TEST_CASE_COLUMNS, s.tables.cases ?? [], ["requirement", "description"]) }],
};
