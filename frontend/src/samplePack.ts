import type { Brief, FlowKind, Opportunity, Process, ViewModel } from "./types";

/** Build sample ViewModel display fields from the i18n pack; merge API evaluation. */
export function sampleFromPack(
  s: {
    text: string;
    steps: string[];
    opps: {
      name: string; problem: string; improvement: string; value: string; effort: string;
      humans: string; assume: string; flow: string[][];
    }[];
    brief: [string, string | null, string[] | null][];
    brief_note: string;
  },
  api: {
    opportunities?: Opportunity[];
    providers: ViewModel["providers"];
    proposals: ViewModel["proposals"];
    evaluation?: ViewModel["evaluation"];
  },
): ViewModel {
  const process: Process = {
    process_name: "Incoming inspection",
    environment: "Receiving bay",
    actors: ["security", "store clerk", "inspector", "supervisor"],
    tools: ["paper register", "vernier caliper", "Excel"],
    steps: s.steps.map((text, i) => ({
      id: `s${i + 1}`,
      text,
      kind: i < 5 ? "observation" : "assumption",
      evidence_ref: i < 5 ? "description" : null,
      manual: false,
      decision_point: false,
      data_entry: text.toLowerCase().includes("excel") || text.toLowerCase().includes("writes"),
    })),
    pain_points: [],
    missing_fields: [],
  };

  const FLOW_KINDS: FlowKind[][] = [
    ["change", "remove", "change", "human"],
    ["same", "change", "change"],
    ["change", "change", "human"],
  ];
  const opportunities: Opportunity[] = s.opps.map((o, i) => {
    const apiO = api.opportunities?.[i];
    const kinds = FLOW_KINDS[i] ?? FLOW_KINDS[0];
    return {
      id: apiO?.id ?? `o${i + 1}`,
      title: o.name,
      description: o.problem,
      recommendation: o.improvement,
      strength: apiO?.strength ?? 12 - i,
      flags: apiO?.flags ?? [],
      evidence_refs: apiO?.evidence_refs ?? [],
      rubric: apiO?.rubric ?? {
        repetitive_work: "high",
        data_availability: "medium",
        ai_feasibility: i === 1 ? "high" : "medium",
        business_impact: "medium",
        implementation_complexity: "medium",
        human_oversight_required: true,
        rule_based_sufficient: i !== 1,
      },
      flow: o.flow.map((pair, j) => ({
        today: pair[0],
        after: pair[1],
        kind: kinds[j] ?? "change",
      })),
    };
  });

  const problem = s.brief.find((b) => b[1])?.[1] ?? "";
  const brief: Brief = {
    problem: String(problem),
    current_workflow: s.steps.slice(0, 5),
    proposed_solution: s.opps[0]?.improvement ?? "",
    ai_approaches: [{ approach: "Workflow + checks", reason: s.opps[0]?.problem ?? "" }],
    required_data: ["Inspection readings", "Tolerance limits"],
    integrations: [],
    human_in_the_loop: [s.opps[0]?.humans ?? ""],
    expected_outcomes: [],
    risks: [],
    phases: [
      { name: "Proof of concept", description: "Pilot on one bay", exit_criteria: "Agreed quality" },
      { name: "Pilot", description: "One site", exit_criteria: "Adoption" },
      { name: "Production", description: "Roll out", exit_criteria: "Stable" },
    ],
    assumptions: [s.opps[0]?.assume ?? ""],
    proposal_requirements: (s.brief.find((b) => b[2])?.[2] ?? []) as string[],
    status: "proposal_only",
    disclaimer: s.brief_note,
    opportunity_id: "o1",
  };

  return {
    isSample: true,
    privacy: [],
    process,
    confirmed: false,
    opportunities,
    brief,
    providers: api.providers,
    proposals: api.proposals,
    evaluation: api.evaluation,
  };
}
