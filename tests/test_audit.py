"""Tests for Module 2 (Portal Auditor). Fully mocked — no live portal or
network access required.
"""

from core.audit import PortalAuditor, findings_to_csv, findings_to_markdown
from core.models import (
    AssociationDef,
    ObjectSchema,
    Owner,
    PortalPipeline,
    PortalPipelineStage,
    PortalPropertyDef,
    PortalSnapshot,
    PortalWorkflow,
    Team,
)
from rules.engine import RulesEngine


class FakeHubSpotClient:
    """Implements the subset of HubSpotClient's interface PortalAuditor calls
    for record-level sampling, with canned data engineered to trip each
    record-based check at least once."""

    def __init__(self):
        self.records_by_object = {
            "contacts": [
                {"id": "1", "properties": {"email": "a@x.com", "lifecyclestage": "Lead"}},
                {"id": "2", "properties": {"email": "b@x.com", "lifecyclestage": "Lead"}},
                {"id": "3", "properties": {"email": "c@x.com"}},
                {"id": "4", "properties": {"email": "d@x.com", "lifecyclestage": "Customer"}},
            ],
            "2-999": [
                {"id": "m1", "properties": {"membership_status": "Active"}},
                {"id": "m2", "properties": {"membership_status": "Paused"}},
            ],
        }
        self.associations = {("2-999", "0-1"): {"m1": ["1"]}}

    def get_records_sample(self, object_type, limit=100, properties=None):
        return list(self.records_by_object.get(object_type, []))[:limit]

    def get_associations_sample(self, from_object_type, to_object_type, object_ids):
        full = self.associations.get((from_object_type, to_object_type), {})
        return {oid: ids for oid, ids in full.items() if oid in object_ids}


def _dirty_snapshot() -> PortalSnapshot:
    contacts = ObjectSchema(
        object_type="contacts",
        label="Contact",
        is_custom=False,
        properties=[
            PortalPropertyDef(name="email", label="Email", type="string", hubspot_defined=True),
            PortalPropertyDef(name="lifecyclestage", label="Lifecycle Stage", type="enumeration", hubspot_defined=True),
            PortalPropertyDef(name="unused_prop", label="Unused Prop", type="string", hubspot_defined=False),
            PortalPropertyDef(name="Lead_Score", label="Lead Score", type="number", hubspot_defined=False),
            PortalPropertyDef(name="lead_source", label="Lead Source", type="string", hubspot_defined=False),
            PortalPropertyDef(name="lead_source_old", label="Lead Source", type="string", hubspot_defined=False),
            PortalPropertyDef(
                name="region",
                label="Region",
                type="enumeration",
                options=["New York", "new york "],
                hubspot_defined=False,
            ),
        ],
    )
    membership = ObjectSchema(
        object_type="2-999",
        label="Memberships",
        is_custom=True,
        singular_label="Memberships",  # intentionally plural -> naming drift
        properties=[
            PortalPropertyDef(name="membership_status", label="Membership Status", type="enumeration", hubspot_defined=False),
        ],
        associations=[
            AssociationDef(from_object="Membership", to_object="0-1", label="Membership to Contact", cardinality="many-to-one")
        ],
    )
    pipeline = PortalPipeline(
        object_type="Deal",
        pipeline_id="p1",
        label="Deal Stages",  # doesn't end with "Pipeline" -> naming drift
        stages=[PortalPipelineStage(stage_id="s1", label="New", display_order=0)],
    )
    workflow = PortalWorkflow(
        workflow_id="w1",
        name="Sync Lifecycle Stage",  # no "|" -> naming drift
        enabled=True,
        object_type="Contact",
        re_enrollment_enabled=True,
        actions=[{"type": "SET_PROPERTY", "propertyName": "lifecyclestage"}],
    )
    owner = Owner(owner_id="1", email="jane@x.com", first_name="Jane", last_name="Doe", teams=[], archived=False)
    team = Team(team_id="10", name="Empty Team", member_count=0)

    return PortalSnapshot(
        pulled_at="2026-01-01T00:00:00+00:00",
        object_schemas=[contacts, membership],
        pipelines=[pipeline],
        workflows=[workflow],
        owners=[owner],
        teams=[team],
    )


def _clean_snapshot() -> PortalSnapshot:
    contacts = ObjectSchema(
        object_type="contacts",
        label="Contact",
        is_custom=False,
        properties=[
            PortalPropertyDef(name="lifecyclestage", label="Lifecycle Stage", type="enumeration", hubspot_defined=True),
        ],
    )
    owner = Owner(owner_id="1", email="jane@x.com", first_name="Jane", last_name="Doe", teams=["Sales"], archived=False)
    team = Team(team_id="10", name="Sales", member_count=1)
    return PortalSnapshot(
        pulled_at="2026-01-01T00:00:00+00:00",
        object_schemas=[contacts],
        pipelines=[],
        workflows=[],
        owners=[owner],
        teams=[team],
    )


class CleanFakeHubSpotClient:
    def get_records_sample(self, object_type, limit=100, properties=None):
        return [
            {"id": "1", "properties": {"lifecyclestage": "Lead"}},
            {"id": "2", "properties": {"lifecyclestage": "Customer"}},
        ]

    def get_associations_sample(self, from_object_type, to_object_type, object_ids):
        return {}


def _auditor(client) -> PortalAuditor:
    return PortalAuditor(client, RulesEngine())


def test_duplicate_property_labels_flagged():
    findings = _auditor(FakeHubSpotClient()).run(_dirty_snapshot())
    assert any("Lead Source" in f.description and f.area == "Properties" for f in findings)


def test_near_duplicate_picklist_values_flagged():
    findings = _auditor(FakeHubSpotClient()).run(_dirty_snapshot())
    assert any("near-duplicate options" in f.description for f in findings)


def test_naming_drift_flags_custom_object_property_workflow_pipeline():
    findings = _auditor(FakeHubSpotClient()).run(_dirty_snapshot())
    naming_findings = [f for f in findings if f.area == "Naming"]
    descriptions = " ".join(f.description for f in naming_findings)
    assert "Custom object naming drift" in descriptions
    assert "Lead_Score" in descriptions
    assert "Workflow 'Sync Lifecycle Stage'" in descriptions
    assert "Pipeline 'Deal Stages'" in descriptions


def test_workflow_reenrollment_and_unconditional_overwrite_flagged_high():
    findings = _auditor(FakeHubSpotClient()).run(_dirty_snapshot())
    workflow_findings = [f for f in findings if f.area == "Workflows"]
    assert len(workflow_findings) == 1
    assert workflow_findings[0].severity == "High"
    assert "re-enrollment" in workflow_findings[0].description.lower()


def test_permission_anomalies_flagged():
    findings = _auditor(FakeHubSpotClient()).run(_dirty_snapshot())
    permission_findings = {f.description: f for f in findings if f.area == "Permissions"}
    assert any("not assigned to any team" in d for d in permission_findings)
    assert any("zero members" in d for d in permission_findings)


def test_unused_and_required_properties_flagged():
    findings = _auditor(FakeHubSpotClient()).run(_dirty_snapshot())
    records_findings = [f for f in findings if f.area == "Records"]
    assert any("unused_prop" in f.description and "no value set" in f.description for f in records_findings)
    required_finding = next(f for f in records_findings if "lifecyclestage" in f.description and "Required" in f.description)
    assert required_finding.severity == "High"
    assert "1 of 4" in required_finding.description


def test_orphaned_records_flagged():
    findings = _auditor(FakeHubSpotClient()).run(_dirty_snapshot())
    assoc_findings = [f for f in findings if f.area == "Associations"]
    assert len(assoc_findings) == 1
    assert "1 of 2" in assoc_findings[0].description
    assert assoc_findings[0].severity == "Medium"


def test_clean_snapshot_produces_no_findings():
    findings = _auditor(CleanFakeHubSpotClient()).run(_clean_snapshot())
    assert findings == []


def test_findings_to_markdown_sorts_by_severity():
    findings = _auditor(FakeHubSpotClient()).run(_dirty_snapshot())
    md = findings_to_markdown(findings)
    assert "# Portal Audit Findings" in md
    high_index = md.find("| High |")
    low_index = md.find("| Low |")
    assert high_index != -1 and low_index != -1
    assert high_index < low_index


def test_findings_to_csv_round_trips():
    import csv
    import io

    findings = _auditor(FakeHubSpotClient()).run(_dirty_snapshot())
    csv_text = findings_to_csv(findings)
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[0] == ["Severity", "Area", "Object", "Description", "Recommended Fix"]
    assert len(rows) - 1 == len(findings)
