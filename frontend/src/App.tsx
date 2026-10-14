import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { BriefView, EvaluationView, OpportunityCard, ProcessMap, ProviderCards, SkeletonBlock } from "./components";
import { Picture } from "./Picture";
import { inr } from "./format";
import type { Process, Question, ViewModel } from "./types";

type Stage = "home" | "show" | "understand" | "discover" | "brief" | "proposals";
const STAGES: { id: Stage; name: string }[] = [
  { id: "show", name: "Show" }, { id: "understand", name: "Understand" }, { id: "discover", name: "Discover" },
  { id: "brief", name: "Brief" }, { id: "proposals", name: "Compare" },
];
const EMPTY: ViewModel = { isSample: false, privacy: [], confirmed: false, opportunities: [], providers: [], proposals: [] };

export default function App() {
  const [stage, setStage] = useState<Stage>("home");
  const [vm, setVm] = useState<ViewModel>(EMPTY);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offerSample, setOfferSample] = useState(false);
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [uploadsEnabled, setUploadsEnabled] = useState(true);
  const [uploadsMessage, setUploadsMessage] = useState(
    "Photo and video upload is temporarily unavailable. Describe your process in text instead.",
  );
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    api.config().then((c) => {
      setUploadsEnabled(c.uploadsEnabled);
      if (c.uploadsDisabledMessage) setUploadsMessage(c.uploadsDisabledMessage);
    }).catch(() => { /* keep defaults if config fails */ });
  }, []);

  const go = useCallback((s: Stage) => {
    setStage(s); setError(null); setOfferSample(false); setRetry(null);
    setTimeout(() => main.current?.focus(), 0);
  }, []);

  const run = useCallback(async (msg: string, fn: () => Promise<void>) => {
    setBusy(msg); setError(null); setOfferSample(false); setRetry(null);
    try { await fn(); } catch (e) {
      const message = e instanceof ApiError || e instanceof Error
        ? e.message
        : "Something went wrong. Please try again or use the sample case.";
      setError(message);
      setOfferSample(
        (e instanceof ApiError && e.status === 429)
          || /sample case|storage|Sign-in failed|capacity|limit/i.test(message),
      );
      setRetry(() => () => { void run(msg, fn); });
    } finally { setBusy(null); }
  }, []);

  const loadSample = () => run("Loading the sample case", async () => {
    const s = await api.sample();
    setVm({
      isSample: true, privacy: [], process: s.process, confirmed: true,
      opportunities: s.opportunities, notAiExplanation: s.notAiExplanation,
      brief: s.brief, providers: s.providers, proposals: s.proposals, evaluation: s.evaluation,
    });
    setSelected("o1"); setOfferSample(false); go("understand");
  });

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="top">
        <button type="button" className="brand" data-testid="brand-home" onClick={() => { setVm(EMPTY); go("home"); }}>
          AI Opportunity Copilot
        </button>
        {stage !== "home" && (
          <nav aria-label="Progress" data-testid="stepper">
            <ol className="stepper">
              {STAGES.map((s) => (
                <li key={s.id} aria-current={stage === s.id ? "step" : undefined} className={stage === s.id ? "on" : ""}>{s.name}</li>
              ))}
            </ol>
          </nav>
        )}
      </header>

      <main id="main" ref={main} tabIndex={-1} data-testid={`stage-${stage}`}>
        <div aria-live="polite" role="status" className="status" data-testid="status">
          {busy ? `${busy}…` : ""}
        </div>
        {busy && <SkeletonBlock label={busy} />}

        {error && (
          <div className="notice warn" role="alert" data-testid="error-banner">
            <p>{error}</p>
            <div className="row">
              {retry && <button type="button" onClick={() => retry()} data-testid="retry">Try again</button>}
              {offerSample && !vm.isSample && (
                <button type="button" className="secondary" onClick={loadSample} disabled={!!busy} data-testid="error-sample">
                  Try the sample case
                </button>
              )}
            </div>
          </div>
        )}

        {vm.isSample && (
          <p className="notice" role="note" data-testid="sample-banner">
            Sample case: read-only walkthrough with simulated providers. No AI calls are made.
          </p>
        )}

        {stage === "home" && (
          <section className="hero-stage" aria-labelledby="home-h" data-testid="home">
            <Picture kind="hero-work" className="hero-media" alt="" priority sizes="100vw" />
            <div className="hero-scrim" aria-hidden="true" />
            <div className="hero-copy">
              <h1 id="home-h">What could AI improve in your work?</h1>
              <p className="lead">Show us how the work is done. We find where AI could help, write a build-ready brief, and compare builder proposals.</p>
              <div className="row">
                <button type="button" data-testid="start-live" onClick={() => { setVm(EMPTY); go("show"); }}>Show us your process</button>
                <button type="button" className="secondary" data-testid="start-sample" onClick={loadSample} disabled={!!busy}>Try the sample case</button>
              </div>
            </div>
          </section>
        )}

        {stage === "show" && (
          <Show
            busy={!!busy}
            uploadsEnabled={uploadsEnabled}
            uploadsMessage={uploadsMessage}
            onSubmit={(file, text) => run(
              uploadsEnabled && file ? "Cleaning your media and analysing the process" : "Analysing the process",
              async () => {
                const { id } = await api.createCase();
                let privacy: string[] = [];
                if (file && uploadsEnabled) privacy = (await api.upload(id, file)).privacy;
                if (text.trim()) await api.describe(id, text);
                const res = await api.analyze(id);
                setVm({ ...EMPTY, caseId: id, privacy, process: res.data });
                go("understand");
              },
            )}
          />
        )}

        {stage === "understand" && vm.process && (
          <Understand
            vm={vm} question={question} busy={!!busy}
            onConfirm={(p) => run("Saving", async () => {
              await api.confirm(vm.caseId!, p);
              const q = await api.question(vm.caseId!);
              setVm({ ...vm, process: p, confirmed: true }); setQuestion(q.question);
            })}
            onAnswer={(field, ans) => run("Saving answer", async () => {
              await api.answer(vm.caseId!, field, ans);
              setQuestion((await api.question(vm.caseId!)).question);
            })}
            onNext={() => vm.isSample ? go("discover") : run("Looking for AI opportunities", async () => {
              const d = await api.discover(vm.caseId!);
              setVm({ ...vm, opportunities: d.opportunities, notAiExplanation: d.notAiExplanation }); go("discover");
            })}
          />
        )}

        {stage === "discover" && (
          <Discover
            vm={vm} selected={selected} setSelected={setSelected} busy={!!busy}
            onBrief={(extra) => vm.isSample ? go("brief") : run("Writing the build brief", async () => {
              const b = await api.brief(vm.caseId!, { opportunity_id: selected!, ...extra });
              setVm({ ...vm, brief: b.data }); go("brief");
            })}
          />
        )}

        {stage === "brief" && vm.brief && (
          <>
            <div className="success-strip" data-testid="brief-success">
              <Picture kind="workshop-dawn" className="tall" alt="" sizes="(max-width: 960px) 100vw, 960px" />
              <p className="notice" role="status">Brief ready. Review it, then compare simulated proposals.</p>
            </div>
            <BriefView brief={vm.brief} />
            <div className="row">
              <button type="button" data-testid="continue-proposals" onClick={() => go("proposals")}>Continue to proposals</button>
            </div>
          </>
        )}

        {stage === "proposals" && (
          <Proposals
            vm={vm} busy={!!busy}
            onSeed={() => run("Requesting simulated proposals", async () => {
              const p = await api.seed(vm.caseId!);
              const s = await api.sample();
              setVm({ ...vm, proposals: p, providers: s.providers });
            })}
            onEvaluate={() => run("Evaluating proposals", async () => {
              const e = await api.evaluate(vm.caseId!);
              setVm({ ...vm, evaluation: e.data });
            })}
            onDelete={() => run("Deleting your case", async () => { await api.remove(vm.caseId!); setVm(EMPTY); go("home"); })}
          />
        )}
      </main>

      <footer className="foot" data-testid="footer">
        <Picture kind="workshop-dawn" className="foot-dawn" alt="" sizes="420px" />
        <p>Providers and proposals are simulated for this prototype. Estimates are ranges based on stated assumptions.</p>
        <p className="foot-disclaimer">Illustrations are AI-generated and do not depict real customers or workplaces.</p>
      </footer>
    </>
  );
}

function Show({ busy, uploadsEnabled, uploadsMessage, onSubmit }: {
  busy: boolean; uploadsEnabled: boolean; uploadsMessage: string;
  onSubmit: (f: File | null, text: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const ok = (uploadsEnabled && !!file) || text.trim().length > 0;
  return (
    <section aria-labelledby="show-h" data-testid="show">
      <h1 id="show-h">Show us how the work happens</h1>
      {uploadsEnabled ? (
        <p className="notice" role="note">
          Before anything is analysed, we blur faces and mask detected sensitive text. Originals are not kept.
          Avoid including customer data. Videos: up to 30 seconds and 20 MB, sampled at one frame per second; audio is ignored.
        </p>
      ) : (
        <p className="notice warn" role="note" data-testid="uploads-off">{uploadsMessage}</p>
      )}
      {uploadsEnabled && (
        <div className="field">
          <label htmlFor="file">Photo or short video</label>
          <input id="file" data-testid="file-input" type="file" accept="image/jpeg,image/png,image/webp,video/mp4" capture="environment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
      )}
      <div className="field">
        <label htmlFor="desc">{uploadsEnabled ? "Describe the process (optional if you add a photo)" : "Describe the process"}</label>
        <textarea
          id="desc" data-testid="process-desc" rows={5} maxLength={4000} value={text}
          onChange={(e) => setText(e.target.value)} required={!uploadsEnabled}
          placeholder="Example: Operators check each part by eye, compare it with a paper checklist, and write the result by hand."
        />
      </div>
      <button type="button" data-testid="analyse" disabled={!ok || busy} onClick={() => onSubmit(uploadsEnabled ? file : null, text)}>
        Analyse my process
      </button>

      <aside className="card privacy-panel" aria-labelledby="privacy-h" data-testid="privacy-panel">
        <Picture kind="privacy-glass" alt="" sizes="(max-width: 640px) 100vw, 140px" />
        <div>
          <h2 id="privacy-h">How your data is protected</h2>
          <ul>
            <li>Only you can open your own cases.</li>
            <li>You can delete a case and its data in one step.</li>
            <li>Daily limits slow abuse of the paid model path.</li>
            <li>Your description is treated as data, not as instructions to the model.</li>
            {!uploadsEnabled && <li>Photo and video upload is off in this hosted demo.</li>}
          </ul>
        </div>
      </aside>
    </section>
  );
}

function Understand({ vm, question, busy, onConfirm, onAnswer, onNext }: {
  vm: ViewModel; question: Question | null; busy: boolean;
  onConfirm: (p: Process) => void; onAnswer: (f: string, a: string) => void; onNext: () => void;
}) {
  const [draft, setDraft] = useState<Process>(vm.process!);
  const [ans, setAns] = useState("");
  const proc = vm.confirmed ? vm.process! : draft;
  return (
    <div data-testid="understand">
      <Picture kind="factory-network" className="stage-banner" alt="" sizes="(max-width: 960px) 100vw, 960px" />
      {vm.privacy.length > 0 && <p className="notice" role="note">Privacy check: {vm.privacy.join("; ")}.</p>}
      <p className="muted">Check this carefully. Items marked Assumption are guesses, not things we saw.</p>
      <ProcessMap process={proc} editable={!vm.confirmed && !vm.isSample} onChange={setDraft} />
      {!vm.confirmed && !vm.isSample && (
        <div className="row">
          <button type="button" data-testid="confirm-process" disabled={busy} onClick={() => onConfirm(draft)}>
            Yes, this is right: continue
          </button>
        </div>
      )}
      {vm.confirmed && !vm.isSample && question && (
        <section aria-labelledby="q-h" className="card" data-testid="follow-up">
          <h2 id="q-h">Question {question.index}</h2>
          <label htmlFor="ans">{question.text}</label>
          <input id="ans" data-testid="answer-input" value={ans} maxLength={500} onChange={(e) => setAns(e.target.value)} />
          <div className="row">
            <button type="button" data-testid="answer" disabled={busy || !ans.trim()} onClick={() => { onAnswer(question.field, ans); setAns(""); }}>Answer</button>
            <button type="button" className="ghost" data-testid="dont-know" disabled={busy} onClick={() => { onAnswer(question.field, "I don't know"); setAns(""); }}>I don't know</button>
          </div>
        </section>
      )}
      {(vm.isSample || (vm.confirmed && !question)) && (
        <div className="row">
          <button type="button" data-testid="find-opportunities" disabled={busy} onClick={onNext}>Find AI opportunities</button>
        </div>
      )}
    </div>
  );
}

function Discover({ vm, selected, setSelected, busy, onBrief }: {
  vm: ViewModel; selected: string | null; setSelected: (s: string) => void; busy: boolean;
  onBrief: (extra: { target_weeks?: number; budget_low_inr?: number; budget_high_inr?: number }) => void;
}) {
  const [weeks, setWeeks] = useState(""); const [low, setLow] = useState(""); const [high, setHigh] = useState("");
  const num = (s: string) => (s.trim() && Number(s) > 0 ? Number(s) : undefined);
  return (
    <div data-testid="discover">
      <h1>Where AI could help</h1>
      {vm.opportunities.length === 0 && (
        <p className="notice" data-testid="not-ai">{vm.notAiExplanation ?? "No strong AI opportunity was found. A simpler workflow change may be enough."}</p>
      )}
      <div className="cards">
        {vm.opportunities.map((o) => (
          <OpportunityCard key={o.id} o={o} selected={selected === o.id} onSelect={() => setSelected(o.id)} />
        ))}
      </div>
      {selected && !vm.isSample && (
        <fieldset className="card">
          <legend>Optional: help us compare proposals fairly</legend>
          <div className="field"><label htmlFor="w">Target delivery time (weeks)</label><input id="w" data-testid="target-weeks" inputMode="numeric" value={weeks} onChange={(e) => setWeeks(e.target.value)} /></div>
          <div className="field"><label htmlFor="bl">Budget from (₹)</label><input id="bl" data-testid="budget-low" inputMode="numeric" value={low} onChange={(e) => setLow(e.target.value)} /></div>
          <div className="field">
            <label htmlFor="bh">Budget up to (₹)</label>
            <input id="bh" data-testid="budget-high" inputMode="numeric" value={high} onChange={(e) => setHigh(e.target.value)} />
            {num(high) && <span className="muted"> {inr(num(high)!)}</span>}
          </div>
        </fieldset>
      )}
      <div className="row">
        <button
          type="button"
          data-testid="generate-brief"
          disabled={!selected || busy}
          onClick={() => onBrief({ target_weeks: num(weeks), budget_low_inr: num(low), budget_high_inr: num(high) })}
        >
          Generate build brief
        </button>
      </div>
    </div>
  );
}

function Proposals({ vm, busy, onSeed, onEvaluate, onDelete }: {
  vm: ViewModel; busy: boolean; onSeed: () => void; onEvaluate: () => void; onDelete: () => void;
}) {
  return (
    <div data-testid="proposals">
      <Picture kind="compare-pillars" className="stage-banner tall" alt="" sizes="(max-width: 960px) 100vw, 960px" />
      <h1>Compare proposals</h1>
      {vm.proposals.length === 0 && (
        <div className="row">
          <button type="button" data-testid="seed-proposals" disabled={busy} onClick={onSeed}>Request simulated proposals</button>
        </div>
      )}
      {vm.proposals.length > 0 && <ProviderCards providers={vm.providers} proposals={vm.proposals} />}
      {vm.proposals.length > 0 && !vm.evaluation && (
        <div className="row">
          <button type="button" data-testid="evaluate" disabled={busy || vm.isSample} onClick={onEvaluate}>Evaluate proposals</button>
        </div>
      )}
      {vm.isSample && vm.evaluation && <EvaluationView ev={vm.evaluation} providers={vm.providers} proposals={vm.proposals} />}
      {!vm.isSample && vm.evaluation && <EvaluationView ev={vm.evaluation} providers={vm.providers} proposals={vm.proposals} />}
      {!vm.isSample && vm.caseId && (
        <div className="row">
          <button type="button" className="ghost" data-testid="delete-case" onClick={onDelete}>Delete this case and its data</button>
        </div>
      )}
    </div>
  );
}
