from app.llm.vertex import vertex_response_schema
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
