"""Test that classification response includes industry detection fields."""
import pytest


def test_classification_schema_has_detection_fields():
    """Verify the classification JSON schema requests industry detection."""
    from app.services.excel_ingestion import SHEET_CLASSIFICATION_SCHEMA

    model_summary = SHEET_CLASSIFICATION_SCHEMA["properties"]["model_summary"]
    props = model_summary["properties"]
    assert "naics_code" in props, "model_summary should have naics_code"
    assert "matched_template_id" in props, "model_summary should have matched_template_id"
    assert "detection_confidence" in props, "model_summary should have detection_confidence"
    assert "detected_revenue_drivers" in props, "model_summary should have detected_revenue_drivers"


def test_classification_schema_has_entity_detection():
    """Verify the classification JSON schema supports multi-entity detection."""
    from app.services.excel_ingestion import SHEET_CLASSIFICATION_SCHEMA

    model_summary = SHEET_CLASSIFICATION_SCHEMA["properties"]["model_summary"]
    props = model_summary["properties"]
    assert "detected_entities" in props, "model_summary should have detected_entities"
    entity_schema = props["detected_entities"]["items"]["properties"]
    assert "entity_name" in entity_schema
    assert "industry" in entity_schema
    assert "is_parent" in entity_schema
    assert "children" in entity_schema
