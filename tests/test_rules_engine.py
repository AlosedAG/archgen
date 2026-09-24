from rules.engine import RulesEngine


def test_custom_object_naming_valid():
    engine = RulesEngine()
    ok, message = engine.check_naming("Membership", "custom_object")
    assert ok
    assert message == ""


def test_custom_object_naming_rejects_plural():
    engine = RulesEngine()
    ok, message = engine.check_naming("Memberships", "custom_object")
    assert not ok
    assert "plural" in message.lower()


def test_custom_object_naming_rejects_lowercase():
    engine = RulesEngine()
    ok, message = engine.check_naming("membership", "custom_object")
    assert not ok


def test_property_naming_valid_snake_case():
    engine = RulesEngine()
    ok, _ = engine.check_naming("membership_status", "property")
    assert ok


def test_property_naming_rejects_camel_case():
    engine = RulesEngine()
    ok, message = engine.check_naming("membershipStatus", "property")
    assert not ok
    assert "snake_case" in message.lower()


def test_workflow_naming_requires_pipe_separator():
    engine = RulesEngine()
    ok, _ = engine.check_naming("Contact | Sync Membership Status", "workflow")
    assert ok
    bad_ok, bad_message = engine.check_naming("Sync Membership Status", "workflow")
    assert not bad_ok
    assert "|" in bad_message


def test_pipeline_naming_requires_pipeline_suffix():
    engine = RulesEngine()
    ok, _ = engine.check_naming("Deal Pipeline", "pipeline")
    assert ok
    bad_ok, _ = engine.check_naming("Deal Stages", "pipeline")
    assert not bad_ok


def test_unknown_naming_kind_raises():
    engine = RulesEngine()
    try:
        engine.check_naming("Foo", "not_a_real_kind")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_overwrite_risk_flags_unconditional_set():
    engine = RulesEngine()
    is_risk, reason = engine.is_overwrite_risk("Set lifecyclestage to Customer")
    assert is_risk
    assert reason


def test_overwrite_risk_allows_conditional_set():
    engine = RulesEngine()
    is_risk, reason = engine.is_overwrite_risk("Set lead source only if blank")
    assert not is_risk
    assert reason == ""


def test_overwrite_risk_ignores_non_write_actions():
    engine = RulesEngine()
    is_risk, _ = engine.is_overwrite_risk("Notify record owner when status changes")
    assert not is_risk


def test_base_currency_rule_present():
    engine = RulesEngine()
    rule = engine.get_base_currency_rule()
    assert rule.get("always_required") is True
    assert "note" in rule


def test_pipeline_template_falls_back_to_generic_custom():
    engine = RulesEngine()
    deal_template = engine.get_pipeline_template("Deal")
    custom_template = engine.get_pipeline_template("Membership")
    generic_template = engine.get_pipeline_template("generic_custom")
    assert deal_template != custom_template
    assert custom_template == generic_template


def test_object_model_keywords_loaded():
    engine = RulesEngine()
    keywords = engine.get_object_model_keywords()
    assert "membership" in keywords
    assert keywords["membership"]["object_name"] == "Membership"


def test_audit_thresholds_have_expected_keys():
    engine = RulesEngine()
    thresholds = engine.get_audit_thresholds()
    assert "record_sample_size" in thresholds
    assert "picklist_similarity_threshold" in thresholds
