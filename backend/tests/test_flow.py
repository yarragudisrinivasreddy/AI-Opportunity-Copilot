"""Opportunity.flow: grounded rows kept; ungrounded dropped; synth only if <3 grounded."""
from app.agents.opportunity import OpportunityAgent
from app.core.flow import (
    ensure_opportunity_flow,
    row_grounded,
    synthesize_flow,
    validate_or_synthesize_flow,
)
from app.llm.fake import FakeLLM, _opportunities
from app.schemas.opportunity import FlowRow, OpportunitySet
from app.schemas.process import Process


def _proc() -> Process:
    return Process.model_validate(
        {
            "process_name": "Inspection",
            "environment": "Floor",
            "actors": ["operator"],
            "tools": ["checklist"],
            "steps": [
                {"id": "s1", "text": "Product placed on the table", "kind": "observation", "evidence_ref": "description"},
                {"id": "s2", "text": "Operator checks the part", "kind": "observation", "evidence_ref": "description"},
                {"id": "s3", "text": "Result written by hand", "kind": "observation", "evidence_ref": "description"},
            ],
            "pain_points": [],
            "missing_fields": [],
        }
    )


def test_synthesize_flow_uses_improvement_not_upstream_phrase():
    rows = synthesize_flow(
        title="Pre-screen",
        description="Flag defects on the line",
        recommendation="candidate",
        human_oversight_required=True,
        process=_proc(),
        improvement="Inspectors enter readings once on a tablet",
        humans_text="Inspector signs off every reading",
    )
    assert 3 <= len(rows) <= 5
    assert any(r.kind == "human" for r in rows)
    assert all(r.today and r.after for r in rows)
    assert all("captured once upstream" not in r.after.lower() for r in rows)
    assert any("tablet" in r.after.lower() for r in rows)
    assert any("signs off" in r.after.lower() for r in rows)


def test_validate_keeps_grounded_drops_ungrounded_without_synth():
    """≥3 grounded after drop → keep them; do not synthesise."""
    model = [
        FlowRow(today="Product placed on the table", after="Still placed on the table", kind="same"),
        FlowRow(today="Operator checks the part", after="Tablet flags out-of-tolerance", kind="change"),
        FlowRow(today="Result written by hand", after="Saved once on the tablet", kind="change"),
        FlowRow(today="A completely unrelated warehouse step", after="Magic AI does stuff", kind="change"),
    ]
    out = validate_or_synthesize_flow(
        model,
        title="T",
        description="Inspectors enter readings once on a tablet",
        recommendation="candidate",
        human_oversight_required=False,
        process=_proc(),
        improvement="Inspectors enter readings once on a tablet",
    )
    assert out.synthesized is False
    assert out.ungrounded_dropped == 1
    assert out.grounded_kept == 3
    assert len(out.rows) == 3
    assert all("unrelated warehouse" not in r.today.lower() for r in out.rows)
    assert all("captured once upstream" not in r.after.lower() for r in out.rows)


def test_live_style_na_human_row_is_dropped():
    """Live EN o1 pattern: model adds human row with today='N/A' — must not display."""
    model = [
        FlowRow(
            today="Security registers the arriving vehicle in a paper register.",
            after="Security scans vehicle registration documents; IDP extracts data.",
            kind="change",
        ),
        FlowRow(
            today="The store clerk manually matches the delivery challan to the corresponding purchase order.",
            after="IDP automatically matches delivery challan to purchase order.",
            kind="change",
        ),
        FlowRow(
            today="The inspector writes the measurement readings on a printed sheet.",
            after="Inspector uses a digital device to record measurements directly.",
            kind="change",
        ),
        FlowRow(
            today="At the end of the day, a data entry operator types the readings into Excel.",
            after="Data is automatically updated in the system.",
            kind="remove",
        ),
        FlowRow(today="N/A", after="Human reviews and validates extracted data and matches.", kind="human"),
    ]
    proc = Process.model_validate(
        {
            "process_name": "Raw Material Receiving",
            "environment": "Gate",
            "actors": ["Security", "store clerk"],
            "tools": ["paper register"],
            "steps": [
                {"id": "s1", "text": "Security registers the arriving vehicle in a paper register.", "kind": "observation", "evidence_ref": "description"},
                {"id": "s2", "text": "The store clerk manually matches the delivery challan to the corresponding purchase order.", "kind": "observation", "evidence_ref": "description"},
                {"id": "s3", "text": "The inspector writes the measurement readings on a printed sheet.", "kind": "observation", "evidence_ref": "description"},
                {"id": "s4", "text": "At the end of the day, a data entry operator types the readings into Excel.", "kind": "observation", "evidence_ref": "description"},
                {"id": "s5", "text": "If a lot fails inspection, the supervisor is notified via phone.", "kind": "observation", "evidence_ref": "description"},
            ],
            "pain_points": [],
            "missing_fields": [],
        }
    )
    out = validate_or_synthesize_flow(
        model,
        title="Automate documents",
        description="IDP for challans",
        recommendation="candidate",
        human_oversight_required=True,
        process=proc,
        improvement="IDP matches challan to PO",
        humans_text="Human reviews and validates extracted data and matches.",
    )
    assert out.synthesized is False
    assert out.ungrounded_dropped >= 1
    assert all(_norm_today(r.today) != "n/a" for r in out.rows)
    assert any(r.kind == "human" for r in out.rows)
    human = next(r for r in out.rows if r.kind == "human")
    assert row_grounded(human.today, proc)


def _norm_today(s: str) -> str:
    return " ".join(s.strip().lower().split())


def test_validate_synthesizes_when_fewer_than_three_grounded_remain():
    """After dropping ungrounded, <3 grounded → synthesise from improvement/humans."""
    model = [
        FlowRow(today="Product placed on the table", after="ok", kind="same"),
        FlowRow(today="Unrelated logistics hop", after="AI invents a hop", kind="change"),
        FlowRow(today="Another invented warehouse scene", after="More invention", kind="change"),
        FlowRow(today="Yet another ungrounded row", after="Still invented", kind="change"),
    ]
    out = validate_or_synthesize_flow(
        model,
        title="Tablet form",
        description="Enter readings once",
        recommendation="candidate",
        human_oversight_required=True,
        process=_proc(),
        improvement="Inspectors enter readings once on a tablet",
        humans_text="Inspector signs off every reading",
    )
    assert out.synthesized is True
    assert out.grounded_kept == 1
    assert out.ungrounded_dropped == 3
    assert len(out.rows) >= 3
    assert all("captured once upstream" not in r.after.lower() for r in out.rows)
    assert any("tablet" in r.after.lower() for r in out.rows)


def test_validate_short_flow_falls_back():
    short = [FlowRow(today="a", after="b", kind="change")]
    out = validate_or_synthesize_flow(
        short,
        title="T",
        description="D",
        recommendation="candidate",
        human_oversight_required=False,
        process=_proc(),
        improvement="A clearer digital step",
    )
    assert out.synthesized is True
    assert len(out.rows) >= 3


def test_agent_fills_flow_when_model_omits_it():
    def handler(system, parts):
        s = _opportunities(system, parts)
        for o in s.opportunities:
            o.flow = []
        return s

    opps, _, audit = OpportunityAgent(FakeLLM({OpportunitySet: handler})).discover(_proc(), {})
    assert all(len(o.flow) >= 3 for o in opps)
    assert any(r.kind == "human" for r in opps[0].flow)
    assert all(a["synthesized"] for a in audit)


def test_ensure_opportunity_flow_for_legacy_doc_without_flow():
    data = {
        "id": "o1",
        "title": "Legacy",
        "description": "Old doc",
        "recommendation": "candidate",
        "rubric": {"human_oversight_required": True},
    }
    out = ensure_opportunity_flow(data, _proc())
    assert len(out["flow"]) >= 3
    assert any(r["kind"] == "human" for r in out["flow"])
    assert all("captured once upstream" not in r["after"].lower() for r in out["flow"])
