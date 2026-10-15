/** Limits from GET /api/config — never hard-code MB/seconds in the UI. */
export type UploadLimits = {
  maxPhotos: number;
  maxPhotoBytes: number;
  maxVideoBytes: number;
  maxVideoSeconds: number;
};

export const DEFAULT_LIMITS: UploadLimits = {
  maxPhotos: 4,
  maxPhotoBytes: 8 * 1024 * 1024,
  maxVideoBytes: 25 * 1024 * 1024,
  maxVideoSeconds: 30,
};

export function mb(bytes: number): string {
  return String(Math.round(bytes / (1024 * 1024)));
}

export function limitVars(lim: UploadLimits): Record<string, string> {
  return {
    p: String(lim.maxPhotos),
    pb: mb(lim.maxPhotoBytes),
    vb: mb(lim.maxVideoBytes),
    vs: String(lim.maxVideoSeconds),
  };
}
