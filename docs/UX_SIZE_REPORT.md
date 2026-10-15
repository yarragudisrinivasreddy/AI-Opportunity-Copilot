# UX / premium UI size report (`ux-overhaul`)

Portal Builder Cup size rule: **not confirmed in portal** — re-check before merge. Prefer lean assets; fonts are large.

## Baseline before premium-ui port (commit ~`7386de9` / prior dist)

| Asset | Bytes |
|---|---|
| Main app JS | 172,205 |
| CSS | 10,440 |
| Images (prior lean set) | 166,374 |
| Fonts | 0 (system) |

**Honesty:** no fake-LLM or FakeImageClient numbers belong in the deck, video, or `evalRuns`.

## After premium-ui-v2 fidelity port (`npm run build`)

| Asset | Bytes |
|---|---|
| Main app JS (`index-MeWLK-k4.js`) | **231,270** |
| CSS (`index-Bnt7SApI.css`) | **30,900** |
| Images (`frontend/public/img/`) | **178,364** |
| Fonts (`frontend/public/fonts/`) | **431,928** |

v2 adds journey/jstep/media DOM + packs; uploads remain off in production until Part 2b.

Hero remains the only preloaded image. Indic fonts use `unicode-range` (downloaded only when glyphs appear).
