from app.llm.vertex import vertex_response_schema
from app.schemas.opportunity import OpportunitySet
from app.schemas.process import Process


def test_vertex_schema_strips_constraints_and_refs():
    schema = vertex_response_schema(Process)
    blob = str(schema)
    assert "minLength" not in blob
    assert "maxLength" not in blob
    assert "minItems" not in blob
    assert "$ref" not in blob
    assert "$defs" not in schema
    assert schema["type"] == "object"
    assert "steps" in schema["properties"]


def test_vertex_schema_keeps_fields_named_title_and_description():
    """Regression: stripping JSON-Schema meta keys must not drop property names."""
    schema = vertex_response_schema(OpportunitySet)
    items = schema["properties"]["opportunities"]["items"]["properties"]
    assert "title" in items and "description" in items
    assert "repetitive_work" in items["rubric"]["properties"]
