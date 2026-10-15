/** Screen fragments matched to design/premium-ui/app.js DOM (sample + live). */
import { useState } from "react";
import { useRef } from "react";
import { Badge, EvaluationView, FlowView, ProcessMap, ProviderCards, SheetHead } from "./components";
import { Icon } from "./icons";
import { useI18n } from "./i18n";
import { Picture } from "./Picture";
import type { Process, Question, ViewModel } from "./types";

const OPP_KIND = ["simple", "ai", "simple"] as const;

export function UnderstandScreen({
  vm, busy, onConfirm, onFind, showFind,
}: {
  vm: ViewModel;
  busy: boolean;
  onConfirm: (p: Process) => void;
  onFind: () => void;
  showFind?: boolean;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState<Process>(vm.process!);
  const addRef = useRef<() => void>(() => {});
  const proc = vm.confirmed ? vm.process! : draft;
  const editable = !vm.confirmed;

  return (
    <div data-testid="understand">
      <div className="banner">
        <Picture kind="factory-network" alt="" sizes="100vw" />
        <div>
          <h2>{t("und_ban_h")}</h2>
          <p>{t("und_ban_p")}</p>
        </div>
      </div>
      <SheetHead stage="understand" title={t("und_h")} sub={t("und_sub")} caseName={vm.isSample ? undefined : proc.process_name} />
      {vm.privacy.length > 0 && <p className="notice n-info" role="note">Privacy check: {vm.privacy.join("; ")}.</p>}
      <div className="legend">
        <Badge kind="obs">{t("obs")}</Badge> {t("leg_obs")}
        <Badge kind="asm">{t("asm")}</Badge> {t("leg_asm")}
        <span className="legend-tools">
          <span>{t("steps_n", { n: String(proc.steps.length) })}</span>
          {editable && (
            <button type="button" className="btn btn-quiet btn-sm" data-testid="add-step" onClick={() => addRef.current()}>
              <Icon name="plus" /> {t("add")}
            </button>
          )}
        </span>
      </div>
      <ProcessMap process={proc} editable={editable} onChange={setDraft} onAddRef={(fn) => { addRef.current = fn; }} />
      {!vm.confirmed && (
        <div className="confirm">
          <p>{t("confirm_p")}</p>
          <button type="button" className="btn btn-primary" data-testid="confirm-map" disabled={busy} onClick={() => onConfirm(draft)}>{t("confirm")}</button>
          <button type="button" className="sr" data-testid="confirm-process" onClick={() => onConfirm(draft)} tabIndex={-1} aria-hidden="true">{t("confirm")}</button>
          {vm.isSample && (
            <button type="button" className="sr" data-testid="find-opportunities" onClick={() => onConfirm(draft)} tabIndex={-1} aria-hidden="true">{t("find")}</button>
          )}
        </div>
      )}
      {showFind && (
        <div className="cta-row" style={{ marginTop: 24 }}>
          <button type="button" className="btn btn-primary" data-testid="find-opportunities" disabled={busy} onClick={onFind}>{t("find")}</button>
        </div>
      )}
    </div>
  );
}

export function QuestionsScreen({
  onDone,
}: {
  onDone: () => void;
}) {
  const { t, sample } = useI18n();
  const Q = sample.qs ?? [];
  const [i, setI] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  if (!Q.length) {
    onDone();
    return null;
  }
  const next = () => {
    if (i < Q.length - 1) setI(i + 1);
    else onDone();
  };
  return (
    <div data-testid="questions">
      <SheetHead stage="questions" title={t("q_h")} sub={t("q_sub")} />
      <div className="card q" data-testid="question">
        <div className="q-meta">
          <span>{t("q_of", { i: String(i + 1), n: String(Q.length) })}</span>
          <button type="button" className="btn btn-quiet btn-sm" onClick={next}>{t("skip_q")}</button>
        </div>
        <h2 id="qh">{Q[i].q}</h2>
        <div className="opts" role="radiogroup" aria-labelledby="qh">
          {Q[i].a.map((txt, k) => (
            <button
              key={txt}
              type="button"
              className="opt"
              role="radio"
              aria-checked={answers[i] === k}
              onClick={() => setAnswers({ ...answers, [i]: k })}
            >
              <span className="dot" />{txt}
            </button>
          ))}
        </div>
        <div className="cta-row">
          <button type="button" className="btn btn-primary" data-testid="q-next" disabled={answers[i] == null} onClick={next}>
            {i === Q.length - 1 ? t("find") : t("next")}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Live-path single question (API); sample uses QuestionsScreen. Max 5 (backend MAX_QUESTIONS). */
const LIVE_Q_FALLBACK_TOTAL = 5;

export function LiveQuestionCard({
  question, busy, onAnswer,
}: {
  question: Question;
  busy: boolean;
  onAnswer: (field: string, ans: string) => void;
}) {
  const { t } = useI18n();
  const [ans, setAns] = useState("");
  const total = Math.max(question.total ?? LIVE_Q_FALLBACK_TOTAL, question.index);
  const submit = (value: string) => { onAnswer(question.field, value); setAns(""); };
  return (
    <section aria-labelledby="qh" className="card q" data-testid="question">
      <div className="q-meta">
        <span data-testid="q-of">{t("q_of", { i: String(question.index), n: String(total) })}</span>
        <button type="button" className="btn btn-quiet btn-sm" data-testid="dont-know" disabled={busy} onClick={() => submit("I don't know")}>{t("skip_q")}</button>
      </div>
      <h2 id="qh">{question.text}</h2>
      <div className="field">
        <label className="lbl" htmlFor="ans">{t("your_answer")}</label>
        <input
          id="ans"
          type="text"
          data-testid="answer-input"
          value={ans}
          maxLength={500}
          autoComplete="off"
          onChange={(e) => setAns(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && ans.trim() && !busy) submit(ans);
          }}
        />
      </div>
      <div className="cta-row">
        <button type="button" className="btn btn-primary" data-testid="answer" disabled={busy || !ans.trim()} onClick={() => submit(ans)}>{t("answer")}</button>
        <button type="button" className="sr" data-testid="q-next" tabIndex={-1} aria-hidden="true" disabled={busy || !ans.trim()} onClick={() => submit(ans)}>{t("answer")}</button>
      </div>
    </section>
  );
}

export function DiscoverScreen({
  vm, selected, setSelected, visualsEnabled, busy, onBrief,
}: {
  vm: ViewModel;
  selected: string | null;
  setSelected: (id: string) => void;
  visualsEnabled: boolean;
  busy: boolean;
  onBrief: (extra?: { target_weeks?: number; budget_low_inr?: number; budget_high_inr?: number }) => void;
}) {
  const { t, sample } = useI18n();
  const [weeks, setWeeks] = useState("");
  const [low, setLow] = useState("");
  const [high, setHigh] = useState("");
  const num = (s: string) => (s.trim() && Number(s) > 0 ? Number(s) : undefined);

  return (
    <div data-testid="discover">
      <SheetHead stage="discover" title={t("disc_h")} sub={t("disc_sub")} />
      {vm.opportunities.length === 0 && (
        <p className="notice n-info" data-testid="not-ai">{vm.notAiExplanation ?? "No strong AI opportunity was found."}</p>
      )}
      <div className="opps" data-testid="opps">
        {vm.opportunities.map((o, i) => {
          const pack = vm.isSample ? sample.opps[i] : null;
          const kind = pack ? OPP_KIND[i] ?? "simple" : (o.rubric.rule_based_sufficient ? "simple" : "ai");
          return (
            <article key={o.id} className={`card opp${i === 0 ? " best" : ""}`} data-testid={`opp-${"ABC"[i]}`}>
              <div className="opp-head">
                <span className={`verdict v-${kind}`}>
                  {pack?.v ?? (o.rubric.rule_based_sufficient ? "A simple workflow is enough" : "AI could help here")}
                </span>
                <h3>{o.title}</h3>
                {i === 0 && <Badge kind="ok">{t("best")}</Badge>}
              </div>
              <dl className="facts">
                <div><dt>{t("problem")}</dt><dd>{pack?.problem ?? o.description}</dd></div>
                <div><dt>{t("improvement")}</dt><dd>{pack?.improvement ?? o.recommendation}</dd></div>
                <div><dt>{t("value")}</dt><dd>{pack?.value ?? o.rubric.business_impact} <Badge kind="est">{t("estimate")}</Badge></dd></div>
                <div><dt>{t("effort")}</dt><dd>{pack?.effort ?? o.rubric.implementation_complexity} <Badge kind="est">{t("estimate")}</Badge></dd></div>
                <div><dt>{t("humans")}</dt><dd>{pack?.humans ?? (o.rubric.human_oversight_required ? "Human oversight required" : "Low ongoing oversight")}</dd></div>
              </dl>
              <div className="opp-foot">
                <span className="hint" style={{ margin: 0 }}>{t("assumes")}{pack?.assume ?? ""}</span>
                <button
                  type="button"
                  className={`btn btn-sm ${i === 0 ? "btn-primary" : "btn-quiet"}`}
                  data-testid={`select-opportunity-${o.id}`}
                  aria-pressed={selected === o.id}
                  onClick={() => {
                    setSelected(o.id);
                    if (vm.isSample) onBrief();
                  }}
                >
                  {t("write_brief")}
                </button>
                {vm.isSample && i === 0 && (
                  <button
                    type="button"
                    className="sr"
                    data-testid="make-brief"
                    tabIndex={-1}
                    aria-hidden="true"
                    onClick={() => { setSelected(o.id); onBrief(); }}
                  >
                    {t("write_brief")}
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
      <FlowView
        opportunities={vm.opportunities}
        process={vm.process}
        selectedId={selected}
        onSelect={setSelected}
        visualsEnabled={visualsEnabled}
        allowStockIllustration={!visualsEnabled || vm.isSample}
        isSample={vm.isSample}
        caseId={vm.caseId}
      />
      {selected && !vm.isSample && (
        <>
          <h2 className="h-page" style={{ marginTop: 48 }}>{t("brief_opts_h")}</h2>
          <p className="sub">{t("brief_opts_p")}</p>
          <fieldset className="card" data-testid="brief-options">
            <legend>{t("brief_opts_legend")}</legend>
            <div className="field">
              <label htmlFor="w">{t("target_weeks")}</label>
              <input id="w" type="text" inputMode="numeric" data-testid="target-weeks" value={weeks} onChange={(e) => setWeeks(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="bl">{t("budget_from")}</label>
              <input id="bl" type="text" inputMode="numeric" data-testid="budget-low" value={low} onChange={(e) => setLow(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="bh">{t("budget_to")}</label>
              <input id="bh" type="text" inputMode="numeric" data-testid="budget-high" value={high} onChange={(e) => setHigh(e.target.value)} />
            </div>
          </fieldset>
          <div className="cta-row" style={{ marginTop: 24 }}>
            <button
              type="button"
              className="btn btn-primary"
              data-testid="make-brief"
              disabled={busy}
              onClick={() => onBrief({ target_weeks: num(weeks), budget_low_inr: num(low), budget_high_inr: num(high) })}
            >
              {t("write_brief")}
            </button>
            <button
              type="button"
              className="sr"
              data-testid="generate-brief"
              tabIndex={-1}
              aria-hidden="true"
              disabled={busy}
              onClick={() => onBrief({ target_weeks: num(weeks), budget_low_inr: num(low), budget_high_inr: num(high) })}
            >
              {t("write_brief")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export function BriefScreen({ vm, onCompare }: { vm: ViewModel; onCompare: () => void }) {
  const { t, sample } = useI18n();
  const [copied, setCopied] = useState(false);
  const B = sample.brief;
  const copy = async () => {
    try {
      const md = `# ${sample.brief_title}\n\n> ${sample.brief_note}\n\n` + B.map(([a, p, l]) => `## ${a}\n\n${p || ""}${l ? l.map((x) => `- ${x}`).join("\n") : ""}`).join("\n\n");
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* ignore */ }
  };
  return (
    <div data-testid="brief-view">
      <SheetHead stage="brief" title={t("brief_h")} />
      <div className="disclaimer" data-testid="disclaimer"><b>{t("disc_b")}</b>{t("disc_d")}</div>
      <div className="brief-top">
        <span className="hint" style={{ margin: 0 }}>{t("based_on")}{sample.opps[0]?.name ?? vm.brief?.opportunity_id}</span>
        <button type="button" className="btn btn-quiet" data-testid="copy-md" onClick={copy}>{copied ? t("copied") : t("copy_md")}</button>
      </div>
      {vm.isSample ? (
        <div className="acc">
          {B.map(([a, p, l], k) => (
            <details key={a} open={k < 2}>
              <summary>{a}</summary>
              <div className="body">
                {p ? <p>{p}</p> : null}
                {l ? <ul>{l.map((x) => <li key={x}>{x}</li>)}</ul> : null}
              </div>
            </details>
          ))}
        </div>
      ) : (
        vm.brief && (
          <div className="acc" data-testid="brief-disclaimer">
            <p className="notice n-info" role="note">{vm.brief.disclaimer}</p>
            <details open><summary>Problem</summary><div className="body"><p>{vm.brief.problem}</p></div></details>
            <details open><summary>Proposed solution</summary><div className="body"><p>{vm.brief.proposed_solution}</p></div></details>
            <details><summary>Phases</summary><div className="body"><ol>{vm.brief.phases.map((p) => <li key={p.name}><strong>{p.name}</strong>: {p.description}</li>)}</ol></div></details>
          </div>
        )
      )}
      <div className="cta-row" style={{ marginTop: 24 }}>
        <button type="button" className="btn btn-primary" data-testid="to-compare" onClick={onCompare}>{t("to_compare")}</button>
        <button type="button" className="sr" data-testid="continue-proposals" onClick={onCompare} tabIndex={-1} aria-hidden="true">{t("to_compare")}</button>
      </div>
      <section className="done-strip">
        <Picture kind="workshop-dawn" alt="" sizes="100vw" />
        <div>
          <h2>{t("done_h")}</h2>
          <p style={{ color: "#cfdbdd" }}>{t("done_p")}</p>
        </div>
      </section>
    </div>
  );
}

export function CompareScreen({
  vm, busy, onSeed, onPaste, onEvaluate, onDelete,
}: {
  vm: ViewModel;
  busy?: boolean;
  onSeed?: () => void;
  onPaste?: (text: string, name: string) => void;
  onEvaluate?: () => void;
  onDelete?: () => void;
}) {
  const { t, sample } = useI18n();
  const [pasteText, setPasteText] = useState("");
  const [pasteName, setPasteName] = useState("");
  const pastedCount = vm.proposals.filter((p) => (p as { pasted?: boolean }).pasted).length;
  const crit = ["Fit", "Cost", "Timeline", "Risk", "Clarity"] as const;
  const scores = [
    { Fit: 9, Cost: 7, Timeline: 8, Risk: 8, Clarity: 9, flags: [] as string[], rank: 1 },
    { Fit: 8, Cost: 8, Timeline: 5, Risk: 6, Clarity: 7, flags: ["weeks"], rank: 2 },
    { Fit: 7, Cost: 5, Timeline: 7, Risk: 6, Clarity: 6, flags: [] as string[], rank: 3 },
    { Fit: 5, Cost: 6, Timeline: 6, Risk: 3, Clarity: 4, flags: ["inject"], rank: 4 },
  ];
  const providers = sample.providers;
  const total = (s: (typeof scores)[0]) => Math.round(crit.reduce((a, c) => a + s[c], 0) / crit.length * 10);

  if (vm.isSample) {
    return (
      <div data-testid="proposals">
        <div className="banner">
          <Picture kind="compare-pillars" alt="" sizes="100vw" />
          <div>
            <h2>{t("cmp_ban_h")}</h2>
            <p data-testid="compare-banner-count">{t("cmp_ban_p", { n: String(providers.length) })}</p>
          </div>
        </div>
        <SheetHead stage="proposals" title={t("cmp_h")} hideTitle />
        <div className="notice n-info"><div><b>{t("scored_b")}</b>{t("scored_d")}</div></div>
        <div className="notice n-warn" style={{ margin: "16px 0 24px" }} role="note" data-testid="injection-notice"
          data-flagged-name={providers.find((_, i) => scores[i].flags.includes("inject"))?.name ?? ""}>
          <div>
            <b>{t("flagged_b")}</b>
            {t("flagged_d", { name: providers.find((_, i) => scores[i].flags.includes("inject"))?.name ?? "Orchid Digital" })}
          </div>
        </div>
        <div className="pc" data-testid="cards">
          {providers.map((p, k) => {
            const s = scores[k];
            return (
              <article key={p.name} className={`card pcard${k === 0 ? " first" : ""}`} data-testid={`provider-${k + 1}`}>
                <div className="pc-head">
                  <span className="rank" aria-label={t("rank", { i: String(k + 1) })}>{k + 1}</span>
                  <div>
                    <h3>{p.name}</h3>
                    <div className="tags">
                      <Badge kind="sim">{t("sim")}</Badge>
                      {s.flags.includes("inject") && <Badge kind="asm">{t("flag_steer")}</Badge>}
                      {s.flags.includes("weeks") && <Badge kind="est">{t("weeks_inf")}</Badge>}
                    </div>
                  </div>
                </div>
                <p className="verd">{p.verdict}</p>
                <ul className="bars">
                  {crit.map((c) => (
                    <li key={c}>
                      <span>{t(`c_${c}` as "c_Fit")}</span>
                      <span className="bar-track" role="img" aria-label={`${t(`c_${c}` as "c_Fit")} ${s[c]}/10`}>
                        <span className={`bar-fill${s[c] <= 5 ? " lo" : ""}`} style={{ width: `${s[c] * 10}%` }} />
                      </span>
                      <b>{s[c]}</b>
                    </li>
                  ))}
                </ul>
                <p className="verd" data-testid={`overall-sample-${k}`}>
                  <span>{t("overall")}</span>{" "}
                  <strong>{total(s)}</strong>
                </p>
                <details>
                  <summary>{t("wrote")}</summary>
                  <div className="dtl">
                    <span><b>{t("price")}</b>{p.price} <Badge kind="est">{t("estimate")}</Badge></span>
                    <span><b>{t("timeline")}</b>{p.weeks}</span>
                    <span>{p.text}</span>
                    {p.quote ? <span className="quote">“{p.quote}”</span> : null}
                  </div>
                </details>
              </article>
            );
          })}
        </div>
        <div className="tablewrap card" data-testid="table">
          <table>
            <caption className="sr">{t("cap")}</caption>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">{t("provider")}</th>
                {crit.map((c) => <th key={c} scope="col">{t(`c_${c}` as "c_Fit")}</th>)}
                <th scope="col">{t("overall")}</th>
              </tr>
            </thead>
            <tbody>
              {providers.map((p, k) => (
                <tr key={p.name}>
                  <td>{k + 1}</td>
                  <td className="prov">
                    <strong>{p.name}</strong>
                    <span className="tags">
                      <Badge kind="sim">{t("sim")}</Badge>
                      {scores[k].flags.includes("inject") && <Badge kind="asm">{t("flag_steer")}</Badge>}
                      {scores[k].flags.includes("weeks") && <Badge kind="est">{t("weeks_inf")}</Badge>}
                    </span>
                    <span className="hint">{p.verdict}</span>
                  </td>
                  {crit.map((c) => <td key={c} className="n">{scores[k][c]}</td>)}
                  <td className="n">{total(scores[k])}/100</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div data-testid="evaluation-view" className="sr" aria-hidden="true">evaluation</div>
        <div data-testid="compare-desktop" className="sr" aria-hidden="true" />
        <div data-testid="compare-mobile" className="sr" aria-hidden="true" />
        <p className="hint" style={{ marginTop: 16 }}>{t("inf_note")}</p>
      </div>
    );
  }

  const simCount = vm.evaluation
    ? vm.evaluation.ranking.filter((id) => {
        const p = vm.providers.find((x) => x.id === id) ?? vm.proposals.find((x) => x.providerId === id);
        return p?.simulated !== false;
      }).length
    : vm.proposals.filter((p) => p.simulated).length;

  return (
    <div data-testid="proposals">
      <div className="banner">
        <Picture kind="compare-pillars" alt="" sizes="100vw" />
        <div>
          <h2>{t("cmp_ban_h")}</h2>
          <p data-testid="compare-banner-count">
            {simCount > 0 ? t("cmp_ban_p", { n: String(simCount) }) : t("cmp_h")}
          </p>
        </div>
      </div>
      <SheetHead stage="proposals" title={t("cmp_h")} hideTitle />
      {vm.proposals.length === 0 && onSeed && (
        <div className="cta-row">
          <button type="button" className="btn btn-primary" data-testid="seed-proposals" disabled={busy} onClick={onSeed}>
            Load and score simulated proposals
          </button>
        </div>
      )}
      {vm.evaluation && <EvaluationView ev={vm.evaluation} providers={vm.providers} proposals={vm.proposals} />}
      {vm.proposals.length > 0 && !vm.evaluation && (
        <>
          <ProviderCards providers={vm.providers} proposals={vm.proposals} />
          {onEvaluate && (
            <div className="cta-row">
              <button type="button" className="btn btn-primary" data-testid="evaluate" disabled={busy} onClick={onEvaluate}>Evaluate proposals</button>
            </div>
          )}
        </>
      )}
      {onPaste && pastedCount < 5 && (
        <details className="card pad paste-details" style={{ marginTop: 32 }} data-testid="paste-proposal">
          <summary style={{ fontSize: "var(--t-3)", fontStretch: "88%", cursor: "pointer" }}>{t("paste_details")}</summary>
          <p className="hint" style={{ margin: "12px 0" }}>
            {t("paste_hint", { n: String(pastedCount) })}
          </p>
          <label className="lbl" htmlFor="paste-name">Provider name</label>
          <input id="paste-name" type="text" data-testid="paste-name" value={pasteName} maxLength={80}
            onChange={(e) => setPasteName(e.target.value)} placeholder="e.g. Acme Systems" />
          <label className="lbl" htmlFor="paste-body" style={{ marginTop: 12 }}>Proposal text</label>
          <textarea id="paste-body" data-testid="paste-body" rows={6} maxLength={20000} value={pasteText}
            onChange={(e) => setPasteText(e.target.value)} placeholder="Paste the full proposal here…" />
          <div className="cta-row" style={{ marginTop: 16 }}>
            <button
              type="button"
              className="btn btn-quiet"
              data-testid="paste-submit"
              disabled={busy || pasteText.trim().length < 40}
              onClick={() => { onPaste(pasteText.trim(), pasteName.trim() || "Pasted proposal"); setPasteText(""); }}
            >
              Add pasted proposal
            </button>
          </div>
        </details>
      )}
      {!vm.isSample && vm.caseId && onDelete && (
        <div className="cta-row delete-case-row" style={{ marginTop: 48 }}>
          <button type="button" className="btn btn-quiet" data-testid="delete-case" onClick={onDelete}>Delete this case and its data</button>
        </div>
      )}
    </div>
  );
}
