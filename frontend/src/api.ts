import { authHeaders } from "./auth";
import type { Evaluation, Opportunity, Process, Question } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function call<T>(method: string, path: string, body?: unknown, form?: FormData, opts?: { auth?: boolean }): Promise<T> {
  const headers: Record<string, string> = opts?.auth === false ? {} : { ...(await authHeaders()) };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api${path}`, { method, headers, body: form ?? (body !== undefined ? JSON.stringify(body) : undefined) });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.");
  return data as T;
}

export const api = {
  // Public: no auth — sample must work even when anonymous sign-in / storage is blocked.
  sample: () => call<any>("GET", "/sample", undefined, undefined, { auth: false }),
  config: () => call<{ uploadsEnabled: boolean; uploadsDisabledMessage: string }>("GET", "/config", undefined, undefined, { auth: false }),
  createCase: () => call<{ id: string }>("POST", "/cases", {}),
  upload: (id: string, file: File) => { const f = new FormData(); f.append("file", file); return call<{ frames: number; privacy: string[] }>("POST", `/cases/${id}/media`, undefined, f); },
  describe: (id: string, text: string) => call<void>("PUT", `/cases/${id}/description`, { text }),
  analyze: (id: string) => call<{ data: Process }>("POST", `/cases/${id}/analyze`),
  confirm: (id: string, process?: Process) => call<{ data: Process }>("POST", `/cases/${id}/process/confirm`, { process: process ?? null }),
  question: (id: string) => call<{ question: Question | null }>("GET", `/cases/${id}/question`),
  answer: (id: string, field: string, answer: string) => call<void>("POST", `/cases/${id}/answers`, { field, answer }),
  discover: (id: string) => call<{ opportunities: Opportunity[]; notAiExplanation: string | null }>("POST", `/cases/${id}/discover`),
  brief: (id: string, body: { opportunity_id: string; target_weeks?: number; budget_low_inr?: number; budget_high_inr?: number }) => call<{ data: any }>("POST", `/cases/${id}/brief`, body),
  seed: (id: string) => call<any[]>("POST", `/cases/${id}/proposals/seed`),
  evaluate: (id: string, weights?: Record<string, number>) => call<{ data: Evaluation }>("POST", `/cases/${id}/evaluate`, { weights: weights ?? null }),
  remove: (id: string) => call<void>("DELETE", `/cases/${id}`),
};
