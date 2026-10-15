import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { flowFor } from "./flow";
import { inr, label, pct } from "./format";
import { Icon, JOURNEY_STAGES, type IconName } from "./icons";
import { useI18n } from "./i18n";
import { Picture } from "./Picture";
import type { Brief, Evaluation, FlowKind, FlowRow, Opportunity, Process, ProposalDoc, Provider, Step } from "./types";

export function Badge({ kind, children }: { kind: "obs" | "asm" | "sim" | "ok" | "est" | "warn"; children: React.ReactNode }) {
  const cls = kind === "obs" ? "b-obs" : kind === "asm" ? "b-asm" : kind === "sim" ? "b-sim" : kind === "ok" ? "b-ok" : kind === "est" ? "b-est" : "b-asm";
  return <span className={`badge ${cls}`}>{children}</span>;
}

export function SheetHead({
  stage, title, sub, caseName, hideTitle = false,
}: {
  stage: "show" | "understand" | "questions" | "discover" | "brief" | "proposals";
  title: string;
  sub?: string;
  caseName?: string;
  /** When the page already has a banner heading (Compare), skip the duplicate h1. */
  hideTitle?: boolean;
}) {
  const { t } = useI18n();
  // Count STAGES (5). Questions shares Understand as step 2.
  const stageIdx = JOURNEY_STAGES.findIndex((s) => s.stages.includes(stage));
  const stepI = String(stageIdx + 1);
  const stepN = String(JOURNEY_STAGES.length);
  return (
    <>
      <div className="titleblock">
        <div><small>{t("case_label")}</small><strong>{caseName || t("case_name")}</strong></div>
        <div><small>{t("step_label")}</small><strong>{t("step_of", { i: stepI, n: stepN })}</strong></div>
      </div>
      <ol className="jstep" aria-label={`${t("step_label")} ${t("step_of", { i: stepI, n: stepN })}`} data-testid="stepper">
        {JOURNEY_STAGES.map((s, n) => {
          const cur = s.stages.includes(stage);
          return (
            <li key={s.key} className={n < stageIdx ? "done" : cur ? "now" : ""} aria-current={cur ? "step" : undefined}>
              <span className="jn"><Icon name={s.key as IconName} /></span>
              <span className="jl">{t(s.key)}</span>
            </li>
          );
        })}
      </ol>
      {hideTitle ? <h1 className="sr">{title}</h1> : <h1 className="h-page">{title}</h1>}
      {sub ? <p className="sub">{sub}</p> : null}
    </>
  );
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

export function ProcessMap({ process, editable, onChange, onAddRef }: {
  process: Process; editable?: boolean; onChange?: (p: Process) => void;
  onAddRef?: (add: () => void) => void;
}) {
  const { t, sample } = useI18n();
  const [editing, setEditing] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");

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
  const add = () => {
    const s = newStep(process.steps.length);
    s.text = t("new_step");
    onChange?.({ ...process, steps: [...process.steps, s] });
    setEditing(s.id);
    setDraftText(s.text);
  };
  useEffect(() => { onAddRef?.(add); });

  const evFor = (s: Step, i: number) => {
    if (s.manual) return t("added_by");
    if (s.kind === "observation") {
      return (sample.ev_obs ?? "Your description, sentence {n}").replace("{n}", String(i + 2));
    }
    const asms = sample.ev_asm ?? [];
    const obsCount = process.steps.filter((x) => x.kind === "observation").length;
    return asms[i - obsCount] ?? t("leg_asm");
  };

  return (
    <section aria-labelledby="map-h" data-testid="process-map">
      <h2 id="map-h" className="sr">{process.process_name}</h2>
      <ol className="route" aria-label="Process steps in order">
        {process.steps.map((s, i) => {
          const isEd = editable && editing === s.id;
          return (
            <li key={s.id} className={s.kind === "observation" ? "obs" : "asm"} data-testid={`step-${s.id}`}>
              <span className="node" aria-hidden="true">{i + 1}</span>
              <div className={`step${isEd ? " editing" : ""}`}>
                <div className="step-top">
                  {s.kind === "observation"
                    ? <Badge kind="obs">{t("obs")}</Badge>
                    : <Badge kind="asm">{s.manual ? t("asm_added") : t("asm")}</Badge>}
                </div>
                {isEd ? (
                  <textarea
                    aria-label={t("edit_aria", { i: String(i + 1) })}
                    data-testid={`edit-${s.id}`}
                    value={draftText}
                    maxLength={500}
                    rows={3}
                    onChange={(e) => setDraftText(e.target.value)}
                  />
                ) : (
                  <h3>{s.text}</h3>
                )}
                <p className="ev">
                  <b>{s.kind === "observation" ? t("evidence") : t("why")}</b>
                  {evFor(s, i)}
                </p>
                {editable && (
                  <div className="step-tools">
                    {isEd ? (
                      <>
                        <button type="button" className="btn btn-primary btn-sm" onClick={() => { update(i, draftText.trim() || s.text); setEditing(null); }}>{t("save")}</button>
                        <button type="button" className="btn btn-quiet btn-sm" onClick={() => setEditing(null)}>{t("cancel")}</button>
                      </>
                    ) : (
                      <>
                        <button type="button" className="icon-btn" disabled={i === 0} onClick={() => move(i, -1)} aria-label={t("up", { i: String(i + 1) })}><Icon name="up" /></button>
                        <button type="button" className="icon-btn" disabled={i === process.steps.length - 1} onClick={() => move(i, 1)} aria-label={t("down", { i: String(i + 1) })}><Icon name="down" /></button>
                        <button type="button" className="icon-btn" onClick={() => { setEditing(s.id); setDraftText(s.text); }} aria-label={t("edit", { i: String(i + 1) })}><Icon name="edit" /></button>
                        {process.steps.length > 1 && (
                          <button type="button" className="icon-btn" onClick={() => remove(i)} aria-label={t("del", { i: String(i + 1) })}><Icon name="del" /></button>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function OpportunityCard({ o, selected, onSelect, letter, best }: {
  o: Opportunity; selected: boolean; onSelect?: () => void; letter?: string; best?: boolean;
}) {
  const { t } = useI18n();
  return (
    <article
      className={`card opp${best ? " best" : ""}${selected ? " selected" : ""}`}
      aria-labelledby={`o-${o.id}`}
      data-testid={letter ? `opp-${letter}` : `opportunity-${o.id}`}
    >
      {best && <div className="verdict v-simple">{t("best")}</div>}
      <h3 id={`o-${o.id}`}>{o.title}</h3>
      <dl className="opp-meta">
        <div><dt>{t("problem")}</dt><dd>{o.description}</dd></div>
        <div><dt>{t("improvement")}</dt><dd>{o.recommendation}</dd></div>
        <div><dt>{t("value")}</dt><dd>{label(o.rubric.business_impact)} · strength {o.strength}/15</dd></div>
        <div><dt>{t("effort")}</dt><dd><Badge kind="est">{t("estimate")}</Badge> {label(o.rubric.implementation_complexity)}</dd></div>
        <div><dt>{t("humans")}</dt><dd>{o.rubric.human_oversight_required ? "Human oversight required" : "Low ongoing oversight"}</dd></div>
      </dl>
      <div className="opp-foot">
        {o.flags.length > 0 && <span className="hint">{o.flags.join(" · ")}</span>}
        {onSelect && (
          <button type="button" className={`btn btn-sm ${selected || best ? "btn-primary" : "btn-quiet"}`} onClick={onSelect} aria-pressed={selected} data-testid={`select-opportunity-${o.id}`}>
            {t("write_brief")}
          </button>
        )}
      </div>
    </article>
  );
}

const KIND_KEY: Record<FlowKind, "f_same" | "f_change" | "f_remove" | "f_human"> = {
  same: "f_same", change: "f_change", remove: "f_remove", human: "f_human",
};

export function FlowView({
  opportunities, process, selectedId, onSelect, visualsEnabled, allowStockIllustration = false, isSample = false, caseId,
}: {
  opportunities: Opportunity[];
  process?: Process;
  selectedId: string | null;
  onSelect: (id: string) => void;
  visualsEnabled: boolean;
  /** Show shipped per-opportunity WebPs (sample always; live when VISUALS off). */
  allowStockIllustration?: boolean;
  /** Sample uses AI-example caption; live uses “not generated from your process”. */
  isSample?: boolean;
  caseId?: string | null;
}) {
  const { t } = useI18n();
  const [concept, setConcept] = useState<"idle" | "busy" | "ready" | "off" | "hidden">("idle");
  const [conceptUrl, setConceptUrl] = useState<string | null>(null);
  const idx = Math.max(0, opportunities.findIndex((o) => o.id === selectedId));
  const active = opportunities[idx] ?? opportunities[0];
  const rows: FlowRow[] = active ? flowFor(active, process) : [];
  const showBlock = visualsEnabled || allowStockIllustration;
  const stockKind = (["concept-opp-a", "concept-opp-b", "concept-opp-c"] as const)[
    Math.min(idx, 2)
  ];

  const showConcept = () => {
    if (!allowStockIllustration && !visualsEnabled) {
      setConcept("hidden");
      return;
    }
    if (allowStockIllustration) {
      setConcept("busy");
      window.setTimeout(() => setConcept("ready"), 900);
      return;
    }
    // Live Vertex path — only when kill switch is on.
    if (!caseId || !active?.id) {
      setConcept("off");
      return;
    }
    setConcept("busy");
    void api.visual(caseId, active.id).then((res) => {
      if (res.status === "ready" && res.dataUrl) {
        setConceptUrl(res.dataUrl);
        setConcept("ready");
      } else {
        setConcept("off");
      }
    }).catch(() => setConcept("off"));
  };

  if (!opportunities.length) return null;

  return (
    <section aria-labelledby="flow-h" data-testid="flow" style={{ marginTop: 48 }}>
      <h2 id="flow-h" className="h-page">{t("flow_h")}</h2>
      <p className="sub" style={{ marginBottom: 16 }}>{t("flow_sub")}</p>
      <div className="tabs" role="tablist" aria-label={t("flow_h")}>
        {opportunities.map((o, i) => (
          <button
            key={o.id}
            type="button"
            className="tab"
            role="tab"
            id={`tab${i}`}
            aria-selected={o.id === (selectedId ?? active?.id)}
            aria-controls="flowpanel"
            data-testid={`flow-tab-${i}`}
            onClick={() => { onSelect(o.id); setConcept("idle"); }}
          >
            {t("pick")} {"ABC"[i]}
          </button>
        ))}
      </div>
      <div id="flowpanel" role="tabpanel" aria-labelledby={`tab${idx}`}>
        <div className="fhead" aria-hidden="true">
          <span>{t("today")}</span><span /><span>{t("after")}</span>
        </div>
        <ol className="flow">
          {rows.map((r, i) => (
            <li key={i} className="frow">
              <div className="fcell today"><small>{t("today")}</small><span>{r.today}</span></div>
              <div className="farrow" aria-hidden="true"><Icon name="arrow" /></div>
              <div className={`fcell after k-${r.kind}`}>
                <small>{t("after")}</small>
                <span className="fk">{t(KIND_KEY[r.kind])}</span>
                <span>{r.after}</span>
              </div>
            </li>
          ))}
        </ol>
        {showBlock && (
          <div className="vis" data-testid="concept-area">
            <h3 style={{ fontSize: "var(--t-3)", fontStretch: "88%" }}>{t("vis_h")}</h3>
            {concept === "idle" && (
              <button type="button" className="btn btn-quiet" style={{ marginTop: 12 }} data-testid="concept-btn" onClick={showConcept}>
                {allowStockIllustration ? t("vis_btn_example") : t("vis_btn")}
              </button>
            )}
            {concept === "busy" && <p className="hint" role="status">{t("vis_busy")}</p>}
            {concept === "off" && <div className="notice n-info" style={{ marginTop: 12 }} role="status">{t("vis_off")}</div>}
            {concept === "ready" && allowStockIllustration && (
              <figure data-testid="concept-example">
                <Picture kind={stockKind} alt="" sizes="(max-width: 768px) 100vw, 640px" />
                <figcaption>
                  <Badge kind="est">{t("vis_example_badge")}</Badge>
                  <span>{t(isSample ? "vis_example_cap" : "vis_live_example_cap")}</span>
                </figcaption>
              </figure>
            )}
            {concept === "ready" && !allowStockIllustration && conceptUrl && (
              <figure data-testid="concept-live">
                <img src={conceptUrl} alt="" style={{ width: "100%", height: "auto", borderRadius: "var(--r-md)" }} />
                <figcaption><span>{t("vis_cap")}</span></figcaption>
              </figure>
            )}
          </div>
        )}
      </div>
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

export function BriefView({ brief }: { brief: Brief }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  const md = briefToMarkdown(brief);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked */ }
  };
  const Section = ({ title, children, open }: { title: string; children: React.ReactNode; open?: boolean }) => (
    <details className="acc" open={open}><summary>{title}</summary><div className="body">{children}</div></details>
  );
  return (
    <section aria-labelledby="brief-h" className="brief" data-testid="brief-view">
      <div className="disclaimer" data-testid="disclaimer">
        <b>{t("disc_b")}</b>{t("disc_d")}
      </div>
      <div className="brief-top">
        <h2 id="brief-h">{t("brief_h")}</h2>
        <button type="button" className="btn btn-quiet" onClick={copy} data-testid="copy-md">{copied ? t("copied") : t("copy_md")}</button>
      </div>
      <p className="notice n-info" role="note" data-testid="brief-disclaimer">{brief.disclaimer}</p>
      <Section title="Problem" open>{brief.problem}</Section>
      <Section title="Current workflow" open>
        <ol>{brief.current_workflow.map((s, i) => <li key={i}>{s}</li>)}</ol>
      </Section>
      <Section title="Proposed solution" open><p>{brief.proposed_solution}</p></Section>
      <Section title="Approaches considered">
        <ul>{brief.ai_approaches.map((a) => <li key={a.approach}><strong>{a.approach}</strong>: {a.reason}</li>)}</ul>
      </Section>
      <Section title="Required data">
        <ul>{brief.required_data.map((d) => <li key={d}>{d}</li>)}</ul>
      </Section>
      <Section title="Where people stay involved">
        <ul>{brief.human_in_the_loop.map((d) => <li key={d}>{d}</li>)}</ul>
      </Section>
      <Section title="Phases">
        <ol>{brief.phases.map((p) => <li key={p.name}><strong>{p.name}</strong>: {p.description}</li>)}</ol>
      </Section>
    </section>
  );
}

export function ProviderCards({ providers, proposals }: { providers: Provider[]; proposals: ProposalDoc[] }) {
  const ids = new Set(proposals.map((p) => p.providerId));
  return (
    <div className="pc" data-testid="provider-cards">
      {providers.filter((p) => ids.has(p.id)).map((p, i) => (
        <article key={p.id} className={`card pcard${i === 0 ? " first" : ""}`} data-testid={`provider-${i + 1}`}>
          <h3>{p.name} {p.simulated && <Badge kind="sim">Simulated</Badge>}</h3>
          <p className="hint">{p.capabilities.join(", ")}</p>
        </article>
      ))}
    </div>
  );
}

const CRIT = ["technical_fit", "experience", "timeline", "cost", "risk"] as const;

function scoresAsPercents(text: string): string {
  return text.replace(/\b0\.\d+\b/g, (m) => `${Math.round(parseFloat(m) * 100)}%`);
}

export function EvaluationView({ ev, providers, proposals }: { ev: Evaluation; providers: Provider[]; proposals: ProposalDoc[] }) {
  const { t } = useI18n();
  const name = (id: string) => providers.find((p) => p.id === id)?.name ?? id;
  const readable = (text: string) => scoresAsPercents(
    providers.reduce((acc, p) => acc.split(p.id).join(p.name), text),
  );
  const flaggedIds = ev.extracted.filter((e) => e.injection_flag.detected).map((e) => e.proposal_id);
  const flagged = new Set(flaggedIds);
  const flaggedName = flaggedIds.length ? name(flaggedIds[0]) : "";
  const advisoryIds = ev.extracted
    .filter((e) => !e.injection_flag.detected && (e.injection_flag.reasons || []).includes("model_detected"))
    .map((e) => e.proposal_id);
  const advisory = new Set(advisoryIds);
  const advisoryName = advisoryIds.length ? name(advisoryIds[0]) : "";
  const byId = Object.fromEntries(ev.scores.map((s) => [s.proposal_id, s]));
  const sim = (id: string) => providers.find((p) => p.id === id)?.simulated ?? proposals.find((p) => p.providerId === id)?.simulated ?? true;

  return (
    <section aria-labelledby="eval-h" data-testid="evaluation-view">
      <h2 id="eval-h" className="sr">{t("cmp_h")}</h2>
      {flagged.size > 0 && (
        <div className="notice n-warn" role="alert" data-testid="injection-notice" data-flagged-name={flaggedName}>
          <div><b>{t("flagged_b")}</b>{t("flagged_d", { name: flaggedName })}</div>
        </div>
      )}
      {advisory.size > 0 && (
        <div className="notice n-info" role="status" data-testid="advisory-notice" data-advisory-name={advisoryName}>
          <div><b>{t("advisory_b")}</b>{t("advisory_d", { name: advisoryName })}</div>
        </div>
      )}
      <div className="pc" data-testid="compare-mobile">
        {ev.ranking.map((id, i) => {
          const s = byId[id];
          return (
            <article key={id} className={`card pcard${i === 0 ? " first" : ""}`} data-testid={`compare-card-${id}`}>
              <div className="pc-head">
                <span className="rank">{i + 1}</span>
                <div>
                  <h3>{name(id)}</h3>
                  <div className="tags">
                    {sim(id) && <Badge kind="sim">{t("sim")}</Badge>}
                    {flagged.has(id) && <Badge kind="asm">{t("flag_steer")}</Badge>}
                    {advisory.has(id) && <Badge kind="est">{t("flag_advisory")}</Badge>}
                  </div>
                </div>
              </div>
              <ul className="bars">
                {CRIT.map((c) => (
                  <li key={c}>
                    <span>{label(c)}</span>
                    <span className="bar-track"><span className="bar-fill" style={{ width: `${Math.round((s?.criteria[c] ?? 0) * 100)}%` }} /></span>
                    <b>{pct(s?.criteria[c] ?? 0)}</b>
                  </li>
                ))}
              </ul>
              <p className="verd" data-testid={`overall-${id}`}>
                <span>{t("overall")}</span>{" "}
                <strong>{pct(s?.overall ?? 0)}</strong>
              </p>
            </article>
          );
        })}
      </div>
      <div className="tablewrap card" data-testid="compare-desktop">
        <table>
          <caption className="sr">{t("cap")}</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">{t("provider")}</th>
              {CRIT.map((c) => <th key={c} scope="col">{label(c)}</th>)}
              <th scope="col">{t("overall")}</th>
            </tr>
          </thead>
          <tbody>
            {ev.ranking.map((id, i) => (
              <tr key={id} data-flagged={flagged.has(id) ? "true" : undefined}>
                <td>{i + 1}</td>
                <td className="prov">
                  <strong data-testid={`provider-name-${id}`}>{name(id)}</strong>
                  <span className="tags">
                    {sim(id) && <Badge kind="sim">{t("sim")}</Badge>}
                    {flagged.has(id) && <Badge kind="asm">{t("flag_steer")}</Badge>}
                    {advisory.has(id) && <Badge kind="est">{t("flag_advisory")}</Badge>}
                  </span>
                </td>
                {CRIT.map((c) => <td key={c} className="n">{pct(byId[id]?.criteria[c] ?? 0)}</td>)}
                <td className="n">{pct(byId[id]?.overall ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint" style={{ marginTop: 16 }} data-testid="rationale-summary">{readable(ev.rationale.summary)}</p>
      <span className="sr">{inr(0)}</span>
    </section>
  );
}

/** Modal process hint. List items tick when the caller advances `done` after real API steps — never a timer. */
export function BusyPopup({
  label, media, done = 0,
}: {
  label: string;
  media?: boolean;
  /** Count of finished sub-steps (0 = first in progress). */
  done?: number;
}) {
  const { t } = useI18n();
  const panelRef = useRef<HTMLDivElement>(null);
  const prevFocus = useRef<HTMLElement | null>(null);
  const keys = media
    ? (["busy_m1", "busy_m2", "busy_2", "busy_3"] as const)
    : (["busy_1", "busy_2", "busy_3"] as const);
  useEffect(() => {
    prevFocus.current = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    const focusable = panel?.querySelector<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])");
    (focusable ?? panel)?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || !panel) return;
      const nodes = [...panel.querySelectorAll<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")];
      if (!nodes.length) { e.preventDefault(); panel.focus(); return; }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      prevFocus.current?.focus?.();
    };
  }, []);
  return (
    <div className="busy-backdrop" role="alertdialog" aria-modal="true" aria-labelledby="busy-h" aria-describedby="busy-d" data-testid="busy-popup">
      <div className="busy-panel busy" ref={panelRef} tabIndex={-1}>
        <h2 id="busy-h">{label}</h2>
        <p id="busy-d" className="hint" role="status" aria-live="polite">{t("busy_p")}</p>
        <ol data-testid="busy-steps" data-busy-done={String(done)}>
          {keys.map((k, i) => {
            const cls = i < done ? "ok" : i === done ? "on" : undefined;
            return (
              <li key={k} className={cls} data-testid={`busy-step-${i}`} data-state={cls ?? "pending"}>
                {t(k)}
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

/** @deprecated use BusyPopup */
export function SkeletonBlock({ label, media }: { label: string; media?: boolean }) {
  return <BusyPopup label={label} media={media} />;
}
