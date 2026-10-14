import { useState } from "react";
import { inr, label, pct } from "./format";
import type { Brief, Evaluation, Opportunity, Process, ProposalDoc, Provider, Step } from "./types";

export function Badge({ kind, children }: { kind: "obs" | "assume" | "sim" | "warn" | "ok"; children: React.ReactNode }) {
  return <span className={`badge badge-${kind}`}>{children}</span>;
}

function newStep(i: number): Step {
  return {
    id: `step_new_${Date.now()}_${i}`,
    text: "",
    kind: "assumption",
    evidence_ref: null,
    manual: true,
    decision_point: false,
    data_entry: false,
  };
}

/** Accessible process map: vertical list with connector; keyboard reorder via Up/Down. */
export function ProcessMap({ process, editable, onChange }: {
  process: Process; editable?: boolean; onChange?: (p: Process) => void;
}) {
  const update = (i: number, text: string) =>
    onChange?.({ ...process, steps: process.steps.map((s, j) => (j === i ? { ...s, text } : s)) });
  const remove = (i: number) => onChange?.({ ...process, steps: process.steps.filter((_, j) => j !== i) });
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= process.steps.length) return;
    const steps = [...process.steps];
    [steps[i], steps[j]] = [steps[j], steps[i]];
    onChange?.({ ...process, steps });
  };
  const add = () => onChange?.({ ...process, steps: [...process.steps, newStep(process.steps.length)] });

  return (
    <section className="process-map" aria-labelledby="map-h" data-testid="process-map">
      <h2 id="map-h">{process.process_name}</h2>
      {process.environment && <p className="muted">{process.environment}</p>}
      <ol className="process-steps" aria-label="Process steps in order">
        {process.steps.map((s, i) => (
          <li key={s.id} className="process-step">
            <div className="step-head">
              {s.kind === "observation"
                ? <Badge kind="obs">Observation{s.evidence_ref ? `: ${s.evidence_ref}` : ""}</Badge>
                : <Badge kind="assume">Assumption</Badge>}
              {s.decision_point && <Badge kind="ok">Decision</Badge>}
              {s.data_entry && <Badge kind="ok">Data entry</Badge>}
            </div>
            {editable ? (
              <>
                <label className="sr" htmlFor={`step-${s.id}`}>Step {i + 1} text</label>
                <input id={`step-${s.id}`} value={s.text} maxLength={500} onChange={(e) => update(i, e.target.value)} />
                <div className="step-actions">
                  <button type="button" className="ghost" disabled={i === 0} onClick={() => move(i, -1)} aria-label={`Move step ${i + 1} up`}>Up</button>
                  <button type="button" className="ghost" disabled={i === process.steps.length - 1} onClick={() => move(i, 1)} aria-label={`Move step ${i + 1} down`}>Down</button>
                  {process.steps.length > 1 && (
                    <button type="button" className="ghost" onClick={() => remove(i)} aria-label={`Remove step ${i + 1}`}>Remove</button>
                  )}
                </div>
              </>
            ) : (
              <p>{s.text}</p>
            )}
          </li>
        ))}
      </ol>
      {editable && (
        <div className="row">
          <button type="button" className="secondary" onClick={add} data-testid="add-step">Add step</button>
        </div>
      )}
      {process.pain_points.length > 0 && (
        <>
          <h3>Pain points</h3>
          <ul>{process.pain_points.map((p, i) => (
            <li key={i}>{p.text}{" "}
              <Badge kind={p.kind === "observation" ? "obs" : "assume"}>{p.kind === "observation" ? "Observation" : "Assumption"}</Badge>
            </li>
          ))}</ul>
        </>
      )}
    </section>
  );
}

export function OpportunityCard({ o, selected, onSelect }: { o: Opportunity; selected: boolean; onSelect?: () => void }) {
  return (
    <article className={`card ${selected ? "selected" : ""}`} aria-labelledby={`o-${o.id}`} data-testid={`opportunity-${o.id}`}>
      <h3 id={`o-${o.id}`}>{o.title}</h3>
      <dl className="opp-meta">
        <div><dt>Problem</dt><dd>{o.description}</dd></div>
        <div><dt>Improvement</dt><dd>{o.recommendation}</dd></div>
        <div><dt>Value</dt><dd>{label(o.rubric.business_impact)} business impact · strength {o.strength} of 15</dd></div>
        <div><dt>Effort</dt><dd>{label(o.rubric.implementation_complexity)} to implement · AI feasibility {label(o.rubric.ai_feasibility)}</dd></div>
        <div><dt>Where people stay involved</dt><dd>{o.rubric.human_oversight_required ? "Human oversight required" : "Low ongoing oversight expected"}</dd></div>
      </dl>
      {o.flags.length > 0 && <ul className="flags">{o.flags.map((f) => <li key={f}>{f}</li>)}</ul>}
      {onSelect && (
        <button type="button" onClick={onSelect} aria-pressed={selected} data-testid={`select-opportunity-${o.id}`}>
          {selected ? "Selected" : "Select this opportunity"}
        </button>
      )}
    </article>
  );
}

export function BriefView({ brief }: { brief: Brief }) {
  const [copied, setCopied] = useState(false);
  const md = briefToMarkdown(brief);
  const copy = async () => { await navigator.clipboard.writeText(md); setCopied(true); setTimeout(() => setCopied(false), 1500); };
  const Section = ({ id, title, children, open }: { id: string; title: string; children: React.ReactNode; open?: boolean }) => (
    <details open={open}><summary id={id}>{title}</summary><div>{children}</div></details>
  );
  return (
    <section aria-labelledby="brief-h" className="brief" data-testid="brief-view">
      <div className="row between">
        <h2 id="brief-h">Build brief</h2>
        <button type="button" className="ghost" onClick={copy} data-testid="copy-brief">{copied ? "Copied" : "Copy as Markdown"}</button>
      </div>
      <p className="notice" role="note" data-testid="brief-disclaimer">{brief.disclaimer}</p>
      <p className="muted"><Badge kind="ok">proposal only</Badge> Status: {brief.status}</p>
      <Section id="b-problem" title="Problem" open>{brief.problem}</Section>
      <Section id="b-workflow" title="Current workflow" open>
        <ol>{brief.current_workflow.map((s, i) => <li key={i}>{s}</li>)}</ol>
      </Section>
      <Section id="b-solution" title="Proposed solution" open><p>{brief.proposed_solution}</p></Section>
      <Section id="b-ai" title="Approaches considered">
        <ul>{brief.ai_approaches.map((a) => <li key={a.approach}><strong>{a.approach}</strong>: {a.reason}</li>)}</ul>
      </Section>
      <Section id="b-data" title="Required data">
        <ul>{brief.required_data.map((d) => <li key={d}>{d}</li>)}</ul>
      </Section>
      {brief.integrations.length > 0 && (
        <Section id="b-int" title="Integrations">
          <ul>{brief.integrations.map((d) => <li key={d}>{d}</li>)}</ul>
        </Section>
      )}
      <Section id="b-hitl" title="Where people stay involved">
        <ul>{brief.human_in_the_loop.map((d) => <li key={d}>{d}</li>)}</ul>
      </Section>
      <Section id="b-out" title="Expected outcomes">
        <Badge kind="warn">Estimate</Badge>
        {brief.expected_outcomes.length ? brief.expected_outcomes.map((o) => (
          <p key={o.metric}><strong>{o.metric}:</strong> {o.low} to {o.high} {o.unit}<br /><span className="muted">{o.assumption}</span></p>
        )) : <p className="muted">No estimate shown: volume and time per item were not confirmed.</p>}
      </Section>
      <Section id="b-risks" title="Risks">
        <ul>{brief.risks.map((r) => <li key={r.risk}>{r.risk}<br /><span className="muted">Ask providers: {r.mitigation_prompt}</span></li>)}</ul>
      </Section>
      <Section id="b-phases" title="Phases">
        <ol>{brief.phases.map((p) => <li key={p.name}><strong>{p.name}</strong>: {p.description}<br /><span className="muted">Exit: {p.exit_criteria}</span></li>)}</ol>
      </Section>
      <Section id="b-assumptions" title="Assumptions">
        <ul>{brief.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      </Section>
      <Section id="b-reqs" title="Proposal requirements">
        <ol>{brief.proposal_requirements.map((r, i) => <li key={r}><strong>R{i + 1}</strong> {r}</li>)}</ol>
      </Section>
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
    <ul className="cards" data-testid="provider-cards">
      {providers.filter((p) => ids.has(p.id)).map((p) => (
        <li key={p.id} className="card">
          <h3>{p.name}{" "}{p.simulated && <Badge kind="sim">Simulated</Badge>}</h3>
          <p className="muted">{p.capabilities.join(", ")}</p>
        </li>
      ))}
    </ul>
  );
}

const CRIT = ["technical_fit", "experience", "timeline", "cost", "risk"] as const;

export function EvaluationView({ ev, providers, proposals }: { ev: Evaluation; providers: Provider[]; proposals: ProposalDoc[] }) {
  const name = (id: string) => providers.find((p) => p.id === id)?.name ?? id;
  const readable = (text: string) => providers.reduce((t, p) => t.split(p.id).join(p.name), text);
  const flagged = new Set(ev.extracted.filter((e) => e.injection_flag.detected).map((e) => e.proposal_id));
  const byId = Object.fromEntries(ev.scores.map((s) => [s.proposal_id, s]));
  const sim = (id: string) => providers.find((p) => p.id === id)?.simulated ?? proposals.find((p) => p.providerId === id)?.simulated ?? true;

  return (
    <section aria-labelledby="eval-h" data-testid="evaluation-view">
      <h2 id="eval-h">Proposal evaluation</h2>
      <p className="notice" role="note">
        Scores are computed by code from fields taken from each proposal. The ranking explanation cannot change those scores. Every provider shown is simulated.
      </p>

      <div className="compare-mobile" data-testid="compare-mobile">
        {ev.ranking.map((id, i) => {
          const s = byId[id];
          return (
            <article key={id} className={`card ${i === 0 ? "selected" : ""}`} data-testid={`compare-card-${id}`}>
              <p className="muted">Rank {i + 1}</p>
              <h3>
                {name(id)}{" "}
                {sim(id) && <Badge kind="sim">Simulated</Badge>}{" "}
                {flagged.has(id) && <Badge kind="warn">Injection attempt flagged</Badge>}
              </h3>
              <p><strong>Overall {pct(s.overall)}</strong>
                {i === 0 ? " · Top match for this brief" : i === 1 ? " · Solid alternative" : " · Weaker fit on several criteria"}
              </p>
              <ul className="score-bars">
                {CRIT.map((c) => (
                  <li key={c}>
                    <div className="bar-row"><span>{label(c)}</span><span>{pct(s.criteria[c])}</span></div>
                    <div className="bar-track" aria-hidden="true"><div className="bar-fill" style={{ width: `${Math.round(s.criteria[c] * 100)}%` }} /></div>
                  </li>
                ))}
              </ul>
            </article>
          );
        })}
      </div>

      <div className="compare-desktop scroll" data-testid="compare-desktop">
        <table className="scores">
          <caption className="sr">Scores per proposal and criterion, best first</caption>
          <thead>
            <tr>
              <th scope="col">Rank</th>
              <th scope="col">Provider</th>
              {CRIT.map((c) => <th key={c} scope="col">{label(c)}</th>)}
              <th scope="col">Overall</th>
            </tr>
          </thead>
          <tbody>
            {ev.ranking.map((id, i) => (
              <tr key={id} className={i === 0 ? "best" : ""}>
                <td>{i + 1}</td>
                <th scope="row">
                  {name(id)}{" "}
                  {sim(id) && <Badge kind="sim">Simulated</Badge>}{" "}
                  {flagged.has(id) && <Badge kind="warn">Injection attempt flagged</Badge>}
                </th>
                {CRIT.map((c) => <td key={c}>{pct(byId[id].criteria[c])}</td>)}
                <td><strong>{pct(byId[id].overall)}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {flagged.size > 0 && (
        <p className="notice warn" role="alert" data-testid="injection-notice">
          Instruction-like text in a proposal was detected and removed before analysis. It did not affect any score.
        </p>
      )}
      <h3>Recommendation: {name(ev.rationale.recommended_proposal_id)}</h3>
      <p>{readable(ev.rationale.summary)}</p>
      <ul>{ev.rationale.points.map((p, i) => (
        <li key={i}>{name(p.proposal_id)}: {label(p.criterion)} {pct(p.score)}{" "}
          <span className="muted">(evidence: {p.field_path})</span>
        </li>
      ))}</ul>
      <p className="muted" data-testid="citations-state">
        Explanation source: {ev.rationale_source}{ev.rationale_validated ? ", citations verified" : ", not verified"}.
        {ev.flags.some((f) => f.endsWith("inferred")) && " Target timeline or budget was inferred from the proposals."}
      </p>
      <details>
        <summary>Show submitted proposal text (untrusted input)</summary>
        {proposals.map((p) => (
          <div key={p.id}>
            <h4>{name(p.providerId)} {p.simulated && <Badge kind="sim">Simulated</Badge>}</h4>
            <pre className="raw">{p.rawText}</pre>
          </div>
        ))}
      </details>
    </section>
  );
}

export function SkeletonBlock({ label }: { label: string }) {
  return (
    <div aria-hidden="true" data-testid="skeleton">
      <p className="muted">{label}</p>
      <div className="skeleton block" /><div className="skeleton" /><div className="skeleton" />
    </div>
  );
}

export { inr };
