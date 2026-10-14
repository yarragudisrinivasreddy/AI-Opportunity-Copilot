# UX overhaul size report (`ux-overhaul`)

Portal Builder Cup size rule: **not confirmed in portal from this session** — shipping **lean/** only (~162 KB images). Re-check before merge if the portal hard-caps near 1 MB.

## Images (lean → `frontend/public/img/`)

| File | Bytes |
|---|---|
| hero-work-400.webp | 8,348 |
| hero-work-800.webp | 19,720 |
| hero-work-1600.webp | 51,822 |
| factory-network-800.webp | 35,228 |
| compare-pillars-800.webp | 9,406 |
| privacy-glass-800.webp | 11,792 |
| workshop-dawn-800.webp | 30,058 |
| **Total** | **166,374** (~162.5 KiB) |

## JS/CSS bundle (Vite `frontend/dist`)

| Asset | Before (c83fcf4-era) | After |
|---|---|---|
| Main app JS | 164,927 | 172,205 (+7.3 KB) |
| CSS | 4,132 | 10,440 |
| Firebase/auth chunks | ~248 KB combined | unchanged (~248 KB) |

Hero is the only preloaded image (`hero-work` srcset). Other images are lazy + async decode.
