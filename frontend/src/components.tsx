import { useState } from "react";
import { inr, label, pct } from "./format";
import type { Brief, Evaluation, Opportunity, Process, ProposalDoc, Provider } from "./types";

export function Badge({ kind, children }: { kind: "obs" | "assume" | "sim" | "warn" | "ok"; children: React.ReactNode }) {
  return <span className={`badge badge-${kind}`}>{children}</span>;
}

/** Accessible process map: an ordered list, with the kind written out (never colour alone). */
export function ProcessMap({ process, editable, onChange }: { process: Process; editable?: boolean; onChange?: (p: Process) => void }) {
  const update = (i: number, text: string) => onChange?.({ ...process, steps: process.steps.map((s, j) => (j === i ? { ...s, text } : s)) });
  const remove = (i: number) => onChange?.({ ...process, steps: process.steps.filter((_, j) => j !== i) });
  return (
    <section aria-labelledby="map-h">
      <h2 id="map-h">{process.process_name}</h2>
      {process.environment && <p className="muted">{process.environment}</p>}
      <ol className="steps" aria-label="Process steps in order">
        {process.steps.map((s, i) => (
          <li key={s.id} className="step">
            <div className="step-head">
              {s.kind === "observation" ? <Badge kind="obs">Observation{s.evidence_ref ? `: ${s.evidence_ref}` : ""}</Badge> : <Badge kind="assume">Assumption</Badge>}
              {s.decision_point && <Badge kind="ok">Decision</Badge>}
              {s.data_entry && <Badge kind="ok">Data entry</Badge>}
            </div>
            {editable ? (
              <div className="row">
                <label className="sr" htmlFor={`step-${s.id}`}>Step {i + 1} text</label>
                <input id={`step-${s.id}`} value={s.text} maxLength={500} onChange={(e) => update(i, e.target.value)} />
                {process.steps.length > 1 && <button className="ghost" onClick={() => remove(i)} aria-label={`Remove step ${i + 1}`}>Remove</button>}
              </div>
            ) : (
              <p>{s.text}</p>
            )}
          </li>
        ))}
      </ol>
      {process.pain_points.length > 0 && (
        <>
          <h3>Pain points</h3>
          <ul>{process.pain_points.map((p, i) => <li key={i}>{p.text} <Badge kind={p.kind === "observation" ? "obs" : "assume"}>{label(p.kind)}</Badge></li>)}</ul>
        </>
      )}
    </section>
  );
}

const RUBRIC_ROWS: [keyof Opportunity["rubric"], string][] = [
  ["repetitive_work", "Repetitive work"], ["data_availability", "Data availability"], ["ai_feasibility", "AI feasibility"],
  ["business_impact", "Business impact"], ["implementation_complexity", "Implementation complexity"], ["human_oversight_required", "Human oversight required"],
];

export function OpportunityCard({ o, selected, onSelect }: { o: Opportunity; selected: boolean; onSelect?: () => void }) {
  return (
    <article className={`card ${selected ? "selected" : ""}`} aria-labelledby={`o-${o.id}`}>
      <h3 id={`o-${o.id}`}>{o.title}</h3>
      <p>{o.description}</p>
      <table className="rubric">
        <caption className="sr">Assessment rubric for {o.title}</caption>
        <tbody>
          {RUBRIC_ROWS.map(([k, name]) => (
            <tr key={k}><th scope="row">{name}</th><td>{typeof o.rubric[k] === "boolean" ? (o.rubric[k] ? "Yes" : "No") : label(String(o.rubric[k]))}</td></tr>
          ))}
        </tbody>
      </table>
      <p className="reco"><strong>{o.recommendation}</strong> <span className="muted">(strength {o.strength} of 15)</span></p>
      {o.flags.length > 0 && <ul className="flags">{o.flags.map((f) => <li key={f}>{f}</li>)}</ul>}
      {onSelect && <button onClick={onSelect} aria-pressed={selected}>{selected ? "Selected" : "Select this opportunity"}</button>}
    </article>
  );
}

export function BriefView({ brief }: { brief: Brief }) {
  const [copied, setCopied] = useState(false);
  const md = briefToMarkdown(brief);
  const copy = async () => { await navigator.clipboard.writeText(md); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  return (
    <section aria-labelledby="brief-h" className="brief">
      <div className="row between"><h2 id="brief-h">Build brief</h2><button className="ghost" onClick={copy}>{copied ? "Copied" : "Copy as Markdown"}</button></div>
      <p className="notice" role="note">{brief.disclaimer}</p>
      <h3>Problem</h3><p>{brief.problem}</p>
      <h3>Current workflow</h3><ol>{brief.current_workflow.map((s, i) => <li key={i}>{s}</li>)}</ol>
      <h3>Proposed solution</h3><p>{brief.proposed_solution}</p>
      <h3>AI approaches</h3><ul>{brief.ai_approaches.map((a) => <li key={a.approach}><strong>{a.approach}</strong>: {a.reason}</li>)}</ul>
      <h3>Required data</h3><ul>{brief.required_data.map((d) => <li key={d}>{d}</li>)}</ul>
      {brief.integrations.length > 0 && <><h3>Integrations</h3><ul>{brief.integrations.map((d) => <li key={d}>{d}</li>)}</ul></>}
      <h3>Human in the loop</h3><ul>{brief.human_in_the_loop.map((d) => <li key={d}>{d}</li>)}</ul>
      <h3>Expected outcomes <Badge kind="warn">Estimate</Badge></h3>
      {brief.expected_outcomes.length ? brief.expected_outcomes.map((o) => (
        <p key={o.metric}><strong>{o.metric}:</strong> {o.low} to {o.high} {o.unit}<br /><span className="muted">{o.assumption}</span></p>
      )) : <p className="muted">No estimate shown: volume and time per item were not confirmed.</p>}
      <h3>Risks</h3><ul>{brief.risks.map((r) => <li key={r.risk}>{r.risk}<br /><span className="muted">Ask providers: {r.mitigation_prompt}</span></li>)}</ul>
      <h3>Phases</h3><ol>{brief.phases.map((p) => <li key={p.name}><strong>{p.name}</strong>: {p.description}<br /><span className="muted">Exit: {p.exit_criteria}</span></li>)}</ol>
      <h3>Assumptions</h3><ul>{brief.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      <h3>Proposal requirements</h3><ol>{brief.proposal_requirements.map((r, i) => <li key={r}><strong>R{i + 1}</strong> {r}</li>)}</ol>
    </section>
  );
}

export function briefToMarkdown(b: Brief): string {
  const list = (xs: string[]) => xs.map((x) => `- ${x}`).join("\n");
  return [
    `# Build brief`, `> ${b.disclaimer}`, `## Problem\n${b.problem}`,
    `## Current workflow\n${b.current_workflow.map((s, i) => `${i + 1}. ${s}`).join("\n")}`,
    `## Proposed solution\n${b.proposed_solution}`,
    `## AI approaches\n${b.ai_approaches.map((a) => `- **${a.approach}**: ${a.reason}`).join("\n")}`,
    `## Required data\n${list(b.required_data)}`, `## Human in the loop\n${list(b.human_in_the_loop)}`,
    `## Risks\n${b.risks.map((r) => `- ${r.risk} (ask: ${r.mitigation_prompt})`).join("\n")}`,
    `## Phases\n${b.phases.map((p) => `- **${p.name}**: ${p.description} (exit: ${p.exit_criteria})`).join("\n")}`,
    `## Assumptions\n${list(b.assumptions)}`,
    `## Proposal requirements\n${b.proposal_requirements.map((r, i) => `${i + 1}. R${i + 1}: ${r}`).join("\n")}`,
  ].join("\n\n");
}

export function ProviderCards({ providers, proposals }: { providers: Provider[]; proposals: ProposalDoc[] }) {
  const ids = new Set(proposals.map((p) => p.providerId));
  return (
    <ul className="cards">
      {providers.filter((p) => ids.has(p.id)).map((p) => (
        <li key={p.id} className="card"><h3>{p.name}</h3><p className="muted">{p.capabilities.join(", ")}</p></li>
      ))}
    </ul>
  );
}

export function EvaluationView({ ev, providers, proposals }: { ev: Evaluation; providers: Provider[]; proposals: ProposalDoc[] }) {
  const name = (id: string) => providers.find((p) => p.id === id)?.name ?? id;
  const readable = (text: string) => providers.reduce((t, p) => t.split(p.id).join(p.name), text);
  const flagged = new Set(ev.extracted.filter((e) => e.injection_flag.detected).map((e) => e.proposal_id));
  const byId = Object.fromEntries(ev.scores.map((s) => [s.proposal_id, s]));
  const crit = ["technical_fit", "experience", "timeline", "cost", "risk"];
  return (
    <section aria-labelledby="eval-h">
      <h2 id="eval-h">Proposal evaluation</h2>
      <p className="notice" role="note">Scores are computed by code from fields extracted from each proposal. The model explains the ranking but cannot change it. All providers shown are simulated.</p>
      <div className="scroll">
        <table className="scores">
          <caption className="sr">Scores per proposal and criterion, best first</caption>
          <thead><tr><th scope="col">Rank</th><th scope="col">Provider</th>{crit.map((c) => <th key={c} scope="col">{label(c)}</th>)}<th scope="col">Overall</th></tr></thead>
          <tbody>
            {ev.ranking.map((id, i) => (
              <tr key={id} className={i === 0 ? "best" : ""}>
                <td>{i + 1}</td>
                <th scope="row">{name(id)} {flagged.has(id) && <Badge kind="warn">Injection attempt flagged</Badge>}</th>
                {crit.map((c) => <td key={c}>{pct(byId[id].criteria[c])}</td>)}
                <td><strong>{pct(byId[id].overall)}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {flagged.size > 0 && <p className="notice warn" role="alert">Instruction-like text in a proposal was detected and removed before analysis. It did not affect any score.</p>}
      <h3>Recommendation: {name(ev.rationale.recommended_proposal_id)}</h3>
      <p>{readable(ev.rationale.summary)}</p>
      <ul>{ev.rationale.points.map((p, i) => <li key={i}>{name(p.proposal_id)}: {label(p.criterion)} {pct(p.score)} <span className="muted">(evidence: {p.field_path})</span></li>)}</ul>
      <p className="muted">Explanation source: {ev.rationale_source}{ev.rationale_validated ? ", citations verified" : ", not verified"}. {ev.flags.some((f) => f.endsWith("inferred")) && "Target timeline or budget was inferred from the proposals."}</p>
      <details><summary>Show submitted proposal text (untrusted input)</summary>
        {proposals.map((p) => <div key={p.id}><h4>{name(p.providerId)}</h4><pre className="raw">{p.rawText}</pre></div>)}
      </details>
    </section>
  );
}

export { inr };
