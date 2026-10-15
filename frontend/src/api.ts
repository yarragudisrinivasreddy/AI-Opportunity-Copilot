import { authHeaders } from "./auth";
import type { Evaluation, Opportunity, Process, Provider, Question } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

/** Optional absolute API origin (Cloud Run). Bypasses Hosting's ~60s rewrite timeout on long Vertex calls. */
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";

async function call<T>(method: string, path: string, body?: unknown, form?: FormData, opts?: { auth?: boolean }): Promise<T> {
  const headers: Record<string, string> = opts?.auth === false ? {} : { ...(await authHeaders()) };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API_BASE}/api${path}`, { method, headers, body: form ?? (body !== undefined ? JSON.stringify(body) : undefined) });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.");
  return data as T;
}

export const api = {
  // Public: no auth — sample must work even when anonymous sign-in / storage is blocked.
  sample: () => call<any>("GET", "/sample", undefined, undefined, { auth: false }),
  config: () => call<{
    uploadsEnabled: boolean;
    uploadsDisabledMessage: string;
    visualsEnabled?: boolean;
    maxPhotos?: number;
    maxPhotoBytes?: number;
    maxVideoBytes?: number;
    maxVideoSeconds?: number;
  }>("GET", "/config", undefined, undefined, { auth: false }),
  createCase: () => call<{ id: string }>("POST", "/cases", {}),
  getCase: (id: string) => call<{
    case: { id: string; status: string };
    providers: Provider[];
    proposals: any[];
    evaluation?: { data: Evaluation };
  }>("GET", `/cases/${id}`),
  upload: (id: string, file: File) => { const f = new FormData(); f.append("file", file); return call<{ frames: number; privacy: string[] }>("POST", `/cases/${id}/media`, undefined, f); },
  describe: (id: string, text: string) => call<void>("PUT", `/cases/${id}/description`, { text }),
  analyze: (id: string) => call<{ data: Process }>("POST", `/cases/${id}/analyze`),
  confirm: (id: string, process?: Process) => call<{ data: Process }>("POST", `/cases/${id}/process/confirm`, { process: process ?? null }),
  question: (id: string) => call<{ question: Question | null }>("GET", `/cases/${id}/question`),
  answer: (id: string, field: string, answer: string) => call<void>("POST", `/cases/${id}/answers`, { field, answer }),
  discover: (id: string, language: "en" | "hi" | "te" = "en") =>
    call<{ opportunities: Opportunity[]; notAiExplanation: string | null }>("POST", `/cases/${id}/discover`, { language }),
  brief: (id: string, body: { opportunity_id: string; target_weeks?: number; budget_low_inr?: number; budget_high_inr?: number }) => call<{ data: any }>("POST", `/cases/${id}/brief`, body),
  seed: (id: string) => call<any[]>("POST", `/cases/${id}/proposals/seed`),
  pasteProposal: (id: string, raw_text: string, provider_name?: string) =>
    call<any>("POST", `/cases/${id}/proposals`, { raw_text, provider_name: provider_name ?? "Pasted proposal" }),
  visual: (id: string, opportunityId: string) =>
    call<{ status: string; dataUrl?: string; reason?: string; cached?: boolean; mime?: string }>(
      "POST", `/cases/${id}/opportunities/${opportunityId}/visual`,
    ),
  evaluate: (id: string, weights?: Record<string, number>) => call<{ data: Evaluation }>("POST", `/cases/${id}/evaluate`, { weights: weights ?? null }),
  remove: (id: string) => call<void>("DELETE", `/cases/${id}`),
};
