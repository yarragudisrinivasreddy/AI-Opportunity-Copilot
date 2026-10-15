import type { FlowRow, Opportunity, Process } from "./types";

/** Client-side fallback when an opportunity has no flow (legacy / partial API). */
export function synthesizeFlow(o: Opportunity, process?: Process): FlowRow[] {
  const steps = process?.steps ?? [];
  const todayA = steps[0]?.text ?? `Today: work related to ${o.title}`;
  const todayB = steps[1]?.text ?? "Manual follow-up and re-entry";
  const todayC = steps[2]?.text ?? "Supervisor reviews exceptions by hand";
  const improve = (o.description || o.recommendation || o.title || "A clearer digital step").slice(0, 300);
  const afterRemove = `No longer a separate step — covered by: ${improve.slice(0, 180)}`;
  const humans = o.rubric.human_oversight_required
    ? "A person still reviews exceptions and signs off"
    : "People stay involved only when something is unclear";
  const rows: FlowRow[] = [
    { today: todayA.slice(0, 300), after: improve, kind: "change" },
    { today: todayB.slice(0, 300), after: afterRemove.slice(0, 300), kind: "remove" },
    { today: todayC.slice(0, 300), after: todayC.slice(0, 300), kind: "same" },
  ];
  if (o.rubric.human_oversight_required) {
    rows.push({ today: "A person decides exceptions", after: humans, kind: "human" });
  }
  return rows.slice(0, 5);
}

export function flowFor(o: Opportunity, process?: Process): FlowRow[] {
  if (o.flow && o.flow.length >= 3) return o.flow;
  return synthesizeFlow(o, process);
}
