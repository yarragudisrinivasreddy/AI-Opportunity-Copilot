export type Kind = "observation" | "assumption";
export interface Step { id: string; text: string; kind: Kind; evidence_ref: string | null; manual: boolean; decision_point: boolean; data_entry: boolean }
export interface Process { process_name: string; environment: string; actors: string[]; tools: string[]; steps: Step[]; pain_points: { text: string; kind: Kind; evidence_ref: string | null }[]; missing_fields: string[] }
export interface Rubric { repetitive_work: string; data_availability: string; ai_feasibility: string; business_impact: string; implementation_complexity: string; human_oversight_required: boolean; rule_based_sufficient: boolean }
export interface Opportunity { id: string; title: string; description: string; rubric: Rubric; strength: number; recommendation: string; flags: string[]; evidence_refs: string[] }
export interface Brief {
  problem: string; current_workflow: string[]; proposed_solution: string;
  ai_approaches: { approach: string; reason: string }[]; required_data: string[]; integrations: string[];
  human_in_the_loop: string[]; expected_outcomes: { metric: string; low: number; high: number; unit: string; assumption: string }[];
  risks: { risk: string; mitigation_prompt: string }[]; phases: { name: string; description: string; exit_criteria: string }[];
  assumptions: string[]; proposal_requirements: string[]; status: string; disclaimer: string; opportunity_id: string;
}
export interface Provider { id: string; name: string; simulated: boolean; capabilities: string[] }
export interface ProposalDoc { id: string; providerId: string; simulated: boolean; rawText: string }
export interface Score { proposal_id: string; criteria: Record<string, number>; overall: number }
export interface Evaluation {
  ranking: string[]; scores: Score[]; flags: string[]; rationale_validated: boolean; rationale_source: string;
  rationale: { recommended_proposal_id: string; summary: string; points: { proposal_id: string; criterion: string; score: number; field_path: string }[] };
  extracted: { proposal_id: string; injection_flag: { detected: boolean; reasons: string[]; removed_segments: number } }[];
}
export interface Question { field: string; text: string; index: number }

/** Everything the UI renders, whether it comes from the sample or a live case. */
export interface ViewModel {
  isSample: boolean;
  caseId?: string;
  privacy: string[];
  process?: Process;
  confirmed: boolean;
  opportunities: Opportunity[];
  notAiExplanation?: string | null;
  brief?: Brief;
  providers: Provider[];
  proposals: ProposalDoc[];
  evaluation?: Evaluation;
}
