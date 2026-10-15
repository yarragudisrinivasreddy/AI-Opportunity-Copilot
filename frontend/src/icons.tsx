/** Inline SVG paths from premium-ui-v2/app.js (same-origin, CSP-safe). */
const PATHS = {
  up: "M12 19V5M5 12l7-7 7 7",
  down: "M12 5v14M19 12l-7 7-7-7",
  edit: "M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z",
  del: "M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14",
  plus: "M12 5v14M5 12h14",
  arrow: "M5 12h14M13 6l6 6-6 6",
  j_show: "M4 8h3l2-3h6l2 3h3v11H4zM12 17a4 4 0 100-8 4 4 0 000 8z",
  j_und: "M9 4L3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14",
  j_dis: "M6 4v16M12 4v16M18 4v16M4 9h4M10 15h4M16 8h4",
  j_bri: "M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5",
  j_cmp: "M6 20V12M12 20V5M18 20V9",
  play: "M8 5v14l11-7z",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name }: { name: IconName }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={PATHS[name]} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export const JOURNEY_STAGES = [
  { key: "j_show" as const, stages: ["show"] },
  { key: "j_und" as const, stages: ["understand", "questions"] },
  { key: "j_dis" as const, stages: ["discover"] },
  { key: "j_bri" as const, stages: ["brief"] },
  { key: "j_cmp" as const, stages: ["proposals"] },
];
