import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { BusyPopup, SheetHead } from "./components";
import { DEFAULT_LIMITS, limitVars, type UploadLimits } from "./config";
import { Icon, JOURNEY_STAGES, type IconName } from "./icons";
import { useI18n } from "./i18n";
import { Picture } from "./Picture";
import { sampleFromPack } from "./samplePack";
import {
  BriefScreen,
  CompareScreen,
  DiscoverScreen,
  LiveQuestionCard,
  QuestionsScreen,
  UnderstandScreen,
} from "./screens";
import type { Question, ViewModel } from "./types";

type Stage = "home" | "show" | "understand" | "questions" | "discover" | "brief" | "proposals";
type MediaFile = { file: File; url: string; isVideo: boolean };
const EMPTY: ViewModel = { isSample: false, privacy: [], confirmed: false, opportunities: [], providers: [], proposals: [] };

export default function App() {
  const { t, lang, setLang, langs, name, sample } = useI18n();
  const [stage, setStage] = useState<Stage>("home");
  const [vm, setVm] = useState<ViewModel>(EMPTY);
  const [busy, setBusy] = useState<string | null>(null);
  const [busyMedia, setBusyMedia] = useState(false);
  /** Sub-steps completed in the busy list (advanced only after real API work). */
  const [busyDone, setBusyDone] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [offerSample, setOfferSample] = useState(false);
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [uploadsEnabled, setUploadsEnabled] = useState(false);
  const [visualsEnabled, setVisualsEnabled] = useState(false);
  const [limits, setLimits] = useState<UploadLimits>(DEFAULT_LIMITS);
  const [uploadsMessage, setUploadsMessage] = useState("");
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    api.config().then((c) => {
      setUploadsEnabled(!!c.uploadsEnabled);
      if (c.uploadsDisabledMessage) setUploadsMessage(c.uploadsDisabledMessage);
      if (typeof c.visualsEnabled === "boolean") setVisualsEnabled(c.visualsEnabled);
      setLimits({
        maxPhotos: c.maxPhotos ?? DEFAULT_LIMITS.maxPhotos,
        maxPhotoBytes: c.maxPhotoBytes ?? DEFAULT_LIMITS.maxPhotoBytes,
        maxVideoBytes: c.maxVideoBytes ?? DEFAULT_LIMITS.maxVideoBytes,
        maxVideoSeconds: c.maxVideoSeconds ?? DEFAULT_LIMITS.maxVideoSeconds,
      });
    }).catch(() => { /* keep defaults */ });
  }, []);

  const go = useCallback((s: Stage) => {
    setStage(s); setError(null); setOfferSample(false); setRetry(null);
    setTimeout(() => main.current?.focus(), 0);
  }, []);

  type Progress = { tick: (doneCount: number) => void };
  const run = useCallback(async (
    msg: string,
    fn: (p: Progress) => Promise<void>,
    media = false,
  ) => {
    setBusy(msg); setBusyMedia(media); setBusyDone(0);
    setError(null); setOfferSample(false); setRetry(null);
    const tick = (doneCount: number) => setBusyDone(Math.max(0, doneCount));
    try { await fn({ tick }); } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      // Never surface raw gateway 502 text — same plain Retry + sample path as 503.
      const plainBusy =
        "The AI service is busy right now. Tap Retry in a moment, or open Try the sample case "
        + "(no sign-in, no model cost).";
      let message = e instanceof ApiError || e instanceof Error
        ? e.message
        : "Something went wrong. Please try again or use the sample case.";
      if (status === 502 || status === 503 || /502|Bad Gateway|RESOURCE_EXHAUSTED/i.test(message)) {
        message = plainBusy;
      }
      setError(message);
      setOfferSample(
        (status === 429 || status === 502 || status === 503)
          || /sample case|storage|Sign-in failed|capacity|limit|busy|Retry/i.test(message),
      );
      setRetry(() => () => { void run(msg, fn, media); });
    } finally { setBusy(null); setBusyMedia(false); setBusyDone(0); }
  }, []);

  const loadSample = () => run(t("busy_h"), async ({ tick }) => {
    const s = await api.sample();
    tick(1);
    const vmPack = sampleFromPack(sample, s);
    setVm(vmPack);
    setSelected(vmPack.opportunities[0]?.id ?? "o1");
    setOfferSample(false);
    setQuestion(null);
    tick(2);
    go("understand");
    tick(3);
  });

  const stageSub = (k: string) => (k === "j_show" ? t(uploadsEnabled ? "j_show_s" : "j_show_s_off") : t(`${k}_s` as "j_und_s"));

  return (
    <>
      <a className="skip" href="#main">{t("skip")}</a>
      <header className="bar">
        <div className="wrap">
          <button type="button" className="brand" data-testid="brand-home" onClick={() => { setVm(EMPTY); go("home"); }}>
            <i aria-hidden="true" /> AI Opportunity Copilot
          </button>
          <nav id="nav" aria-label={t("nav_journey")}>
            {([
              ["show", "nav_show"],
              ["understand", "nav_understand"],
              ["discover", "nav_discover"],
              ["brief", "nav_brief"],
              ["proposals", "nav_compare"],
            ] as const).map(([s, key]) => (
              <button
                key={s}
                type="button"
                aria-current={stage === s || (s === "understand" && stage === "questions") ? "true" : undefined}
                data-testid={`nav-${s === "proposals" ? "compare" : s}`}
              >
                {t(key)}
              </button>
            ))}
          </nav>
          <div className="lang" id="langbox">
            <label htmlFor="lang" className="lbl-t">{t("langLabel")}</label>
            <select id="lang" data-testid="lang" aria-label={t("langLabel")} value={lang} onChange={(e) => setLang(e.target.value as typeof lang)}>
              {langs.map((l) => <option key={l} value={l} lang={l}>{name(l)}</option>)}
            </select>
          </div>
        </div>
      </header>

      <main id="main" ref={main} tabIndex={-1} data-testid={`stage-${stage}`}>
        <div aria-live="polite" role="status" className="sr" data-testid="status">{busy ? `${busy}…` : ""}</div>
        {busy && <BusyPopup label={busy} media={busyMedia} done={busyDone} />}

        {error && (
          <div className="wrap">
            <div className="notice n-warn" role="alert" data-testid="error-banner">
              <div>
                <p>{error}</p>
                <div className="cta-row">
                  {retry && <button type="button" className="btn btn-primary" onClick={() => retry()} data-testid="retry">Try again</button>}
                  {offerSample && !vm.isSample && (
                    <button type="button" className="btn btn-quiet" onClick={loadSample} disabled={!!busy} data-testid="error-sample">{t("cta_sample")}</button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {vm.isSample && stage !== "home" && (
          <span className="sr" data-testid="sample-banner">{t("hero_fine")}</span>
        )}

        {stage === "home" && (
          <div data-testid="home">
            <section className="hero" aria-labelledby="home-h">
              <Picture kind="hero-work" alt="" priority sizes="100vw" />
              <div className="wrap">
                <h1 id="home-h">{t("hero_h")}</h1>
                <p className="lede">{t("hero_p")}</p>
                <div className="cta-row">
                  <button type="button" className="btn btn-primary" data-testid="try-sample" onClick={loadSample} disabled={!!busy}>{t("cta_sample")}</button>
                  <button type="button" className="sr" data-testid="start-sample" onClick={loadSample} tabIndex={-1} aria-hidden="true">{t("cta_sample")}</button>
                  <button type="button" className="btn btn-ghost" data-testid="start-own" onClick={() => { setVm(EMPTY); go("show"); }}>{t("cta_own")}</button>
                  <button type="button" className="sr" data-testid="start-live" onClick={() => { setVm(EMPTY); go("show"); }} tabIndex={-1} aria-hidden="true">{t("cta_own")}</button>
                </div>
                <p className="fine">{t("hero_fine")}</p>
              </div>
            </section>

            <section className="band">
              <div className="wrap split">
                <figure><Picture kind="paper-flow" alt="" sizes="(max-width: 768px) 100vw, 50vw" /></figure>
                <div>
                  <h2>{t("split_h")}</h2>
                  <p>{t("split_p")}</p>
                  <ul className="ticks">
                    <li>{t("split_1")}</li>
                    <li>{t("split_2")}</li>
                    <li>{t("split_3")}</li>
                  </ul>
                </div>
              </div>
            </section>

            <section className="band alt" aria-labelledby="gal-h">
              <div className="wrap">
                <h2 id="gal-h" className="h-page">{t("gal_h")}</h2>
                <div className="gal">
                  <article className="tile">
                    <div className="mini" aria-hidden="true">
                      <div className="mrow"><span className="mdot">1</span>{t("g_obs")}<BadgeObs /></div>
                      <div className="mline" />
                      <div className="mrow"><span className="mdot a">2</span>{t("g_asm")}<BadgeAsm /></div>
                    </div>
                    <h3>{t("gal_1t")}</h3>
                    <p>{t("gal_1d")}</p>
                  </article>
                  <article className="tile">
                    <div className="mini" aria-hidden="true">
                      <div className="verdict v-simple">{sample.opps[0]?.v}</div>
                      <b>{t("g_opt")}</b>
                      <div className="mrow"><span className="badge b-est">{t("estimate")}</span>{sample.opps[0]?.effort}</div>
                    </div>
                    <h3>{t("gal_2t")}</h3>
                    <p>{t("gal_2d")}</p>
                  </article>
                  <article className="tile">
                    <div className="mini" aria-hidden="true">
                      <div className="mrow"><b>{t("g_prov")}</b><span className="badge b-sim">{t("sim")}</span></div>
                      {([["c_Fit", 9], ["c_Cost", 7], ["c_Timeline", 8]] as const).map(([k, v]) => (
                        <div className="mbar" key={k}><span>{t(k)}</span><span className="bar-track"><span className="bar-fill" style={{ width: `${v * 10}%` }} /></span></div>
                      ))}
                    </div>
                    <h3>{t("gal_3t")}</h3>
                    <p>{t("gal_3d")}</p>
                  </article>
                </div>
              </div>
            </section>

            <section className="journey" aria-labelledby="jh">
              <Picture kind="factory-network" alt="" sizes="100vw" />
              <div className="wrap">
                <h2 id="jh">{t("journey_h")}</h2>
                <ol className="jhome">
                  {JOURNEY_STAGES.map((s) => (
                    <li key={s.key}>
                      <span className="jn"><Icon name={s.key as IconName} /></span>
                      <b>{t(s.key)}</b>
                      <span>{stageSub(s.key)}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </section>

            <section className="band">
              <div className="wrap">
                <div className="notice n-info">
                  <div><b>{t("who_h")} </b>{t("who_d")}</div>
                </div>
              </div>
            </section>

            <section className="endcta" aria-labelledby="end-h">
              <Picture kind="golden-plant" alt="" sizes="100vw" />
              <div className="wrap">
                <h2 id="end-h">{t("end_h")}</h2>
                <p>{t("end_p")}</p>
                <button type="button" className="btn btn-primary" data-testid="try-sample-2" onClick={loadSample} disabled={!!busy}>{t("cta_sample")}</button>
              </div>
            </section>
          </div>
        )}

        {stage === "show" && (
          <div className="sheet"><div className="wrap">
            <Show
              busy={!!busy}
              uploadsEnabled={uploadsEnabled}
              uploadsMessage={uploadsMessage}
              limits={limits}
              onSample={loadSample}
              onSubmit={(files, text) => run(
                t("busy_h"),
                async ({ tick }) => {
                  const withMedia = uploadsEnabled && files.length > 0;
                  const { id } = await api.createCase();
                  let privacy: string[] = [];
                  if (withMedia) {
                    for (const f of files) {
                      const res = await api.upload(id, f);
                      privacy = [...privacy, ...res.privacy];
                    }
                    tick(1); // busy_m1 done — media accepted / privacy pass
                  }
                  if (text.trim()) await api.describe(id, text);
                  tick(withMedia ? 2 : 1); // busy_m2 or busy_1 — description in; finding steps next
                  const res = await api.analyze(id);
                  tick(withMedia ? 3 : 2); // busy_2 done — steps found; separating next
                  setVm({ ...EMPTY, caseId: id, privacy, process: res.data });
                  tick(withMedia ? 4 : 3); // busy_3 done — hold so the completed list is visible
                  await new Promise((r) => window.setTimeout(r, 400));
                  go("understand");
                },
                uploadsEnabled && files.length > 0,
              )}
            />
          </div></div>
        )}

        {stage === "understand" && vm.process && (
          <div className="sheet"><div className="wrap">
            <UnderstandScreen
              vm={vm}
              busy={!!busy}
              showFind={vm.confirmed && !vm.isSample && !question}
              onConfirm={(p) => {
                if (vm.isSample) {
                  setVm({ ...vm, process: p, confirmed: true });
                  go("questions");
                  return;
                }
                void run("Saving", async ({ tick }) => {
                  await api.confirm(vm.caseId!, p);
                  tick(1);
                  const q = await api.question(vm.caseId!);
                  tick(2);
                  setVm({ ...vm, process: p, confirmed: true });
                  setQuestion(q.question);
                  tick(3);
                });
              }}
              onFind={() => run("Looking for AI opportunities", async ({ tick }) => {
                const d = await api.discover(vm.caseId!, lang);
                tick(2);
                setVm({ ...vm, opportunities: d.opportunities, notAiExplanation: d.notAiExplanation });
                setSelected(d.opportunities[0]?.id ?? null);
                tick(3);
                go("discover");
              })}
            />
            {vm.confirmed && !vm.isSample && question && (
              <LiveQuestionCard
                question={question}
                busy={!!busy}
                onAnswer={(field, ans) => run("Saving answer", async ({ tick }) => {
                  await api.answer(vm.caseId!, field, ans);
                  tick(1);
                  setQuestion((await api.question(vm.caseId!)).question);
                  tick(3);
                })}
              />
            )}
          </div></div>
        )}

        {stage === "questions" && (
          <div className="sheet"><div className="wrap">
            <QuestionsScreen onDone={() => go("discover")} />
          </div></div>
        )}

        {stage === "discover" && (
          <div className="sheet"><div className="wrap">
            <DiscoverScreen
              vm={vm}
              selected={selected}
              setSelected={setSelected}
              busy={!!busy}
              visualsEnabled={visualsEnabled}
              onBrief={(extra) => {
                if (vm.isSample) { go("brief"); return; }
                void run("Writing the build brief", async ({ tick }) => {
                  const b = await api.brief(vm.caseId!, { opportunity_id: selected!, ...extra });
                  tick(2);
                  setVm({ ...vm, brief: b.data });
                  tick(3);
                  go("brief");
                });
              }}
            />
          </div></div>
        )}

        {stage === "brief" && (vm.brief || vm.isSample) && (
          <div className="sheet"><div className="wrap">
            <BriefScreen vm={vm} onCompare={() => go("proposals")} />
          </div></div>
        )}

        {stage === "proposals" && (
          <div className="sheet"><div className="wrap">
            <CompareScreen
              vm={vm}
              busy={!!busy}
              onSeed={() => run("Scoring simulated proposals", async ({ tick }) => {
                const p = await api.seed(vm.caseId!);
                tick(1);
                const e = await api.evaluate(vm.caseId!);
                tick(2);
                // Providers are best-effort; evaluate already succeeded — do not fail the screen if GET lags.
                let providers = vm.providers;
                try {
                  const state = await api.getCase(vm.caseId!);
                  if (state.providers?.length) providers = state.providers;
                } catch { /* keep prior providers; names fall back to ids */ }
                tick(3);
                setVm({
                  ...vm,
                  proposals: p,
                  providers,
                  evaluation: e.data,
                });
              })}
              onPaste={(text, name) => run("Saving pasted proposal", async ({ tick }) => {
                const doc = await api.pasteProposal(vm.caseId!, text, name);
                tick(2);
                const provider = doc.provider ?? {
                  id: doc.providerId, name, capabilities: [], industries: [],
                  typical_range_inr_min: 0, typical_range_inr_max: 0, simulated: false,
                };
                setVm({
                  ...vm,
                  proposals: [...vm.proposals, doc],
                  providers: [...vm.providers.filter((p) => p.id !== provider.id), provider],
                  evaluation: undefined,
                });
                tick(3);
              })}
              onEvaluate={() => run("Evaluating proposals", async ({ tick }) => {
                const e = await api.evaluate(vm.caseId!);
                tick(2);
                setVm({ ...vm, evaluation: e.data });
                tick(3);
              })}
              onDelete={() => run("Deleting your case", async ({ tick }) => {
                await api.remove(vm.caseId!);
                tick(2);
                setVm(EMPTY);
                tick(3);
                go("home");
              })}
            />
          </div></div>
        )}
      </main>

      <footer data-testid="footer">
        <div className="wrap" id="foot">
          <p><b>{t("foot1").split(". ")[0]}. </b>{t("foot1").split(". ").slice(1).join(". ")}</p>
          <p>{t("foot2")}</p>
        </div>
      </footer>
    </>
  );
}

function BadgeObs() { const { t } = useI18n(); return <span className="badge b-obs">{t("obs")}</span>; }
function BadgeAsm() { const { t } = useI18n(); return <span className="badge b-asm">{t("asm")}</span>; }

function Show({ busy, uploadsEnabled, uploadsMessage, limits, onSubmit, onSample }: {
  busy: boolean; uploadsEnabled: boolean; uploadsMessage: string; limits: UploadLimits;
  onSubmit: (files: File[], text: string) => void;
  onSample: () => void;
}) {
  const { t, sample } = useI18n();
  const [text, setText] = useState("");
  const [files, setFiles] = useState<MediaFile[]>([]);
  const [mediaErr, setMediaErr] = useState<string | null>(null);
  const [shortErr, setShortErr] = useState(false);
  const vars = limitVars(limits);

  useEffect(() => () => { files.forEach((f) => URL.revokeObjectURL(f.url)); }, [files]);

  const addFiles = (list: FileList | File[]) => {
    const errs: string[] = [];
    const next = [...files];
    for (const f of Array.from(list)) {
      const isVideo = f.type.startsWith("video/");
      const isImg = f.type.startsWith("image/");
      if (!isVideo && !isImg) { errs.push(t("media_type", { name: f.name })); continue; }
      if (isImg && f.size > limits.maxPhotoBytes) { errs.push(t("media_big", { name: f.name })); continue; }
      if (isVideo && f.size > limits.maxVideoBytes) { errs.push(t("media_big", { name: f.name })); continue; }
      if (isVideo && next.some((x) => x.isVideo)) { errs.push(t("media_count", vars)); continue; }
      if (isImg && next.filter((x) => !x.isVideo).length >= limits.maxPhotos) { errs.push(t("media_count", vars)); continue; }
      next.push({ file: f, url: URL.createObjectURL(f), isVideo });
    }
    setMediaErr(errs.length ? errs.join(" ") : null);
    setFiles(next);
  };

  const removeAt = (k: number) => {
    setFiles((prev) => {
      URL.revokeObjectURL(prev[k].url);
      return prev.filter((_, i) => i !== k);
    });
  };

  return (
    <section aria-labelledby="show-h" data-testid="show">
      <SheetHead stage="show" title={t("show_h")} sub={t("show_sub")} />
      {uploadsEnabled && (
        <section className="card pad media" aria-labelledby="mh" data-testid="media">
          <h2 id="mh" style={{ fontSize: "var(--t-3)", fontStretch: "88%" }}>{t("media_h")}</h2>
          <p className="hint" style={{ marginBottom: 12 }}>{t("media_hint")}</p>
          <input type="file" id="media" className="sr" accept="image/*,video/*" multiple data-testid="media-input"
            onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = ""; }} />
          <label htmlFor="media" className="drop btn btn-quiet"><Icon name="j_show" /> {t("media_add")}</label>
          <p className="hint">{t("media_limits", vars)}</p>
          <p className="hint">{t("media_tip", vars)}</p>
          {mediaErr && <div className="notice n-bad" role="alert" style={{ marginTop: 12 }}>{mediaErr}</div>}
          <ul className="files" data-testid="files">
            {files.map((f, k) => (
              <li key={`${f.file.name}-${k}`}>
                {f.isVideo
                  ? <span className="thumb vid" aria-hidden="true"><Icon name="play" /></span>
                  : <img className="thumb" src={f.url} alt="" width={56} height={56} />}
                <div className="fmeta">
                  <b>{f.file.name}</b>
                  <span>{f.isVideo ? t("media_video") : t("media_photo")} · {(f.file.size / 1048576).toFixed(1)} MB</span>
                  <span className="ok">{t("media_ready")}</span>
                </div>
                <button type="button" className="icon-btn" aria-label={t("media_remove", { name: f.file.name })} data-testid="remove-file" onClick={() => removeAt(k)}>
                  <Icon name="del" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {uploadsEnabled && <div style={{ height: 16 }} />}
      <div className="card pad">
        <label className="lbl" htmlFor="desc">{t("desc_label")}</label>
        {uploadsEnabled && <p className="hint" style={{ margin: "-4px 0 8px" }}>{t("media_or")}</p>}
        <textarea
          id="desc" data-testid="desc" rows={8} maxLength={4000} value={text}
          onChange={(e) => { setText(e.target.value); setShortErr(false); }}
          aria-invalid={shortErr || undefined}
        />
        <textarea className="sr" data-testid="process-desc" aria-hidden="true" tabIndex={-1} value={text} onChange={(e) => setText(e.target.value)} />
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <p className="hint">{t("desc_hint")}</p>
          <p className="hint" aria-live="polite">{text.length} / 4,000</p>
        </div>
        {shortErr && <div className="notice n-bad" role="alert" style={{ marginTop: 12 }}>{t("short_err")}</div>}
        <div className="chips" style={{ marginTop: 16 }} role="group" aria-label={t("example_grp")}>
          <button type="button" className="chip" onClick={() => { setText(sample.text); setShortErr(false); }}>{t("example_btn")}</button>
        </div>
        <div className="cta-row" style={{ marginTop: 24 }}>
          <button type="button" className="btn btn-primary" data-testid="analyse" disabled={busy}
            onClick={() => {
              const hasMedia = uploadsEnabled && files.length > 0;
              if (!hasMedia && text.trim().length < 40) { setShortErr(true); return; }
              onSubmit(files.map((f) => f.file), text);
            }}>
            {t("analyse")}
          </button>
          <button type="button" className="btn btn-quiet" data-testid="sample-link" onClick={onSample}>{t("sample_instead")}</button>
        </div>
      </div>
      {!uploadsEnabled && (
        <div className="notice n-info" style={{ marginTop: 16 }} role="note" data-testid="uploads-off">
          <div><b>{t("uploads_b")}</b>{t("uploads_d")}</div>
        </div>
      )}
      {/* keep API message available for a11y when it differs */}
      {!uploadsEnabled && uploadsMessage && uploadsMessage !== t("uploads_d") && (
        <p className="sr">{uploadsMessage}</p>
      )}
      <aside className="card privacy" aria-labelledby="pv" data-testid="privacy-panel" style={{ marginTop: 24 }}>
        {/* eager: under the busy overlay a lazy image often never paints (looks blank). */}
        <Picture kind="privacy-glass" alt="" sizes="140px" priority />
        <div className="pad">
          <h2 id="pv" style={{ fontSize: "var(--t-3)", fontStretch: "85%" }}>{t("pv_h")}</h2>
          <ul>
            {(uploadsEnabled
              ? ["pv_up_1", "pv_up_2", "pv_up_3", "pv_1", "pv_2", "pv_up_4"]
              : ["pv_1", "pv_2", "pv_3"]
            ).map((k) => <li key={k}>{t(k as "pv_1")}</li>)}
          </ul>
        </div>
      </aside>
    </section>
  );
}
