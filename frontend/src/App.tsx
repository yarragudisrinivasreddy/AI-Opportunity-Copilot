import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { BriefView, EvaluationView, OpportunityCard, ProcessMap, ProviderCards } from "./components";
import { inr } from "./format";
import type { Process, Question, ViewModel } from "./types";

type Stage = "home" | "show" | "understand" | "discover" | "brief" | "proposals";
const STAGES: { id: Stage; name: string }[] = [
  { id: "show", name: "Show" }, { id: "understand", name: "Understand" }, { id: "discover", name: "Discover" },
  { id: "brief", name: "Brief" }, { id: "proposals", name: "Proposals" },
];
const EMPTY: ViewModel = { isSample: false, privacy: [], confirmed: false, opportunities: [], providers: [], proposals: [] };

export default function App() {
  const [stage, setStage] = useState<Stage>("home");
  const [vm, setVm] = useState<ViewModel>(EMPTY);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  const go = useCallback((s: Stage) => { setStage(s); setError(null); setTimeout(() => main.current?.focus(), 0); }, []);
  const run = useCallback(async (msg: string, fn: () => Promise<void>) => {
    setBusy(msg); setError(null);
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again or use the sample case."); } finally { setBusy(null); }
  }, []);

  const loadSample = () => run("Loading the sample case", async () => {
    const s = await api.sample();
    setVm({ isSample: true, privacy: [], process: s.process, confirmed: true, opportunities: s.opportunities, notAiExplanation: s.notAiExplanation,
      brief: s.brief, providers: s.providers, proposals: s.proposals, evaluation: s.evaluation });
    setSelected("o1"); go("understand");
  });

  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="top">
        <button className="brand" onClick={() => { setVm(EMPTY); go("home"); }}>AI Opportunity Copilot</button>
        {stage !== "home" && (
          <nav aria-label="Progress"><ol className="stepper">
            {STAGES.map((s) => <li key={s.id} aria-current={stage === s.id ? "step" : undefined} className={stage === s.id ? "on" : ""}>{s.name}</li>)}
          </ol></nav>
        )}
      </header>
      <main id="main" ref={main} tabIndex={-1}>
        <div aria-live="polite" role="status" className="status">{busy ? `${busy}…` : ""}</div>
        {error && <p className="notice warn" role="alert">{error}</p>}
        {vm.isSample && <p className="notice" role="note">Sample case: read-only walkthrough with simulated providers. No AI calls are made.</p>}

        {stage === "home" && (
          <section className="hero">
            <h1>What could AI improve in your work?</h1>
            <p className="lead">Show us how the work is done. We find where AI could help, write a build-ready brief, and compare builder proposals.</p>
            <div className="row">
              <button onClick={() => { setVm(EMPTY); go("show"); }}>Show us your process</button>
              <button className="secondary" onClick={loadSample} disabled={!!busy}>Try the sample case</button>
            </div>
          </section>
        )}

        {stage === "show" && <Show busy={!!busy} uploadsEnabled={uploadsEnabled} uploadsMessage={uploadsMessage}
          onSubmit={(file, text) => run(uploadsEnabled && file ? "Cleaning your media and analysing the process" : "Analysing the process", async () => {
          const { id } = await api.createCase();
          let privacy: string[] = [];
          if (file && uploadsEnabled) privacy = (await api.upload(id, file)).privacy;
          if (text.trim()) await api.describe(id, text);
          const res = await api.analyze(id);
          setVm({ ...EMPTY, caseId: id, privacy, process: res.data });
          go("understand");
        })} />}

        {stage === "understand" && vm.process && (
          <Understand vm={vm} question={question} busy={!!busy}
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
            })} />
        )}

        {stage === "discover" && (
          <Discover vm={vm} selected={selected} setSelected={setSelected} busy={!!busy}
            onBrief={(extra) => vm.isSample ? go("brief") : run("Writing the build brief", async () => {
              const b = await api.brief(vm.caseId!, { opportunity_id: selected!, ...extra });
              setVm({ ...vm, brief: b.data }); go("brief");
            })} />
        )}

        {stage === "brief" && vm.brief && (
          <>
            <BriefView brief={vm.brief} />
            <div className="row"><button onClick={() => go("proposals")}>Continue to proposals</button></div>
          </>
        )}

        {stage === "proposals" && (
          <Proposals vm={vm} busy={!!busy}
            onSeed={() => run("Requesting simulated proposals", async () => {
              const p = await api.seed(vm.caseId!);
              const s = await api.sample(); // provider names come from the seeded fixtures
              setVm({ ...vm, proposals: p, providers: s.providers });
            })}
            onEvaluate={() => run("Evaluating proposals", async () => {
              const e = await api.evaluate(vm.caseId!);
              setVm({ ...vm, evaluation: e.data });
            })}
            onDelete={() => run("Deleting your case", async () => { await api.remove(vm.caseId!); setVm(EMPTY); go("home"); })} />
        )}
      </main>
      <footer className="foot">Providers and proposals are simulated for this prototype. Estimates are ranges based on stated assumptions.</footer>
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
    <section aria-labelledby="show-h">
      <h1 id="show-h">Show us how the work happens</h1>
      {uploadsEnabled ? (
        <p className="notice" role="note">Before anything is analysed, we blur faces and mask detected sensitive text. Originals are not kept. Avoid including customer data. Videos: up to 30 seconds and 20 MB, sampled at one frame per second; audio is ignored.</p>
      ) : (
        <p className="notice warn" role="note">{uploadsMessage}</p>
      )}
      {uploadsEnabled && (
        <div className="field">
          <label htmlFor="file">Photo or short video (optional)</label>
          <input id="file" type="file" accept="image/jpeg,image/png,image/webp,video/mp4" capture="environment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
      )}
      <div className="field">
        <label htmlFor="desc">{uploadsEnabled ? "Describe the process (optional if you add a photo)" : "Describe the process"}</label>
        <textarea id="desc" rows={5} maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} required={!uploadsEnabled} placeholder="Example: Operators check each part by eye, compare it with a paper checklist, and write the result by hand." />
      </div>
      <button disabled={!ok || busy} onClick={() => onSubmit(uploadsEnabled ? file : null, text)}>Analyse my process</button>
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
    <>
      {vm.privacy.length > 0 && <p className="notice" role="note">Privacy check: {vm.privacy.join("; ")}.</p>}
      <p className="muted">Check this carefully. Items marked Assumption are guesses, not things we saw.</p>
      <ProcessMap process={proc} editable={!vm.confirmed && !vm.isSample} onChange={setDraft} />
      {!vm.confirmed && !vm.isSample && <div className="row"><button disabled={busy} onClick={() => onConfirm(draft)}>Yes, this is right: continue</button></div>}
      {vm.confirmed && !vm.isSample && question && (
        <section aria-labelledby="q-h" className="card">
          <h2 id="q-h">Question {question.index}</h2>
          <label htmlFor="ans">{question.text}</label>
          <input id="ans" value={ans} maxLength={500} onChange={(e) => setAns(e.target.value)} />
          <div className="row">
            <button disabled={busy || !ans.trim()} onClick={() => { onAnswer(question.field, ans); setAns(""); }}>Answer</button>
            <button className="ghost" disabled={busy} onClick={() => { onAnswer(question.field, "I don't know"); setAns(""); }}>I don't know</button>
          </div>
        </section>
      )}
      {(vm.isSample || (vm.confirmed && !question)) && <div className="row"><button disabled={busy} onClick={onNext}>Find AI opportunities</button></div>}
    </>
  );
}

function Discover({ vm, selected, setSelected, busy, onBrief }: {
  vm: ViewModel; selected: string | null; setSelected: (s: string) => void; busy: boolean;
  onBrief: (extra: { target_weeks?: number; budget_low_inr?: number; budget_high_inr?: number }) => void;
}) {
  const [weeks, setWeeks] = useState(""); const [low, setLow] = useState(""); const [high, setHigh] = useState("");
  const num = (s: string) => (s.trim() && Number(s) > 0 ? Number(s) : undefined);
  return (
    <>
      <h1>Where AI could help</h1>
      {vm.opportunities.length === 0 && <p className="notice">{vm.notAiExplanation ?? "No strong AI opportunity was found."}</p>}
      <div className="cards">{vm.opportunities.map((o) => <OpportunityCard key={o.id} o={o} selected={selected === o.id} onSelect={() => setSelected(o.id)} />)}</div>
      {selected && !vm.isSample && (
        <fieldset className="card"><legend>Optional: help us compare proposals fairly</legend>
          <div className="field"><label htmlFor="w">Target delivery time (weeks)</label><input id="w" inputMode="numeric" value={weeks} onChange={(e) => setWeeks(e.target.value)} /></div>
          <div className="field"><label htmlFor="bl">Budget from (₹)</label><input id="bl" inputMode="numeric" value={low} onChange={(e) => setLow(e.target.value)} /></div>
          <div className="field"><label htmlFor="bh">Budget up to (₹)</label><input id="bh" inputMode="numeric" value={high} onChange={(e) => setHigh(e.target.value)} />
            {num(high) && <span className="muted"> {inr(num(high)!)}</span>}</div>
        </fieldset>
      )}
      <div className="row"><button disabled={!selected || busy} onClick={() => onBrief({ target_weeks: num(weeks), budget_low_inr: num(low), budget_high_inr: num(high) })}>Generate build brief</button></div>
    </>
  );
}

function Proposals({ vm, busy, onSeed, onEvaluate, onDelete }: { vm: ViewModel; busy: boolean; onSeed: () => void; onEvaluate: () => void; onDelete: () => void }) {
  return (
    <>
      <h1>Proposals</h1>
      {vm.proposals.length === 0 && <div className="row"><button disabled={busy} onClick={onSeed}>Request simulated proposals</button></div>}
      {vm.proposals.length > 0 && <ProviderCards providers={vm.providers} proposals={vm.proposals} />}
      {vm.proposals.length > 0 && !vm.evaluation && <div className="row"><button disabled={busy || vm.isSample} onClick={onEvaluate}>Evaluate proposals</button></div>}
      {vm.evaluation && <EvaluationView ev={vm.evaluation} providers={vm.providers} proposals={vm.proposals} />}
      {!vm.isSample && vm.caseId && <div className="row"><button className="ghost" onClick={onDelete}>Delete this case and its data</button></div>}
    </>
  );
}
