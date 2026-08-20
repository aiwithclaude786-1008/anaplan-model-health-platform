# Tridant Brand Reference — Anaplan Optimizer

Design tokens applied to the Anaplan Optimizer app (Streamlit chrome + the
Executive Summary HTML dashboard). Each value below is labeled **Measured**
(pulled directly from tridant.com's live computed styles), **Specified**
(given directly by you), or **Derived** (my own reasonable extension where
tridant.com didn't have an equivalent element to sample — e.g. no visible
"error red" on their marketing site).

Source of measured values: right-click → Inspect on the "Book a Discovery
Session" CTA button on tridant.com, Aug 2026.

---

## Colors

### Core brand

| Token | Value | Status | Notes |
|---|---|---|---|
| Accent (brand cyan) | `#00ADEF` / `rgb(0,173,239)` | **Measured** | CTA button `background-color` |
| On-accent text | `#FFFFFF` | **Measured** | CTA button `color` |
| Body text | `#5A5A5A` | **Measured** | Site body/computed text color |
| Header bar background | `#9C66A0` / `rgb(156,102,160)` | **Specified** | Given by you for the report header |

### Derived / supporting palette

| Token | Value | Status | Used for |
|---|---|---|---|
| Accent (hover/deep) | `#0090C9` | Derived | Button hover, links, active tab |
| Heading text | `#2B2E31` | Derived | Headlines, KPI values, strong text |
| Faint text | `#8B9096` | Derived | Labels, captions, timestamps |
| Surface (card bg) | `#F6F8F9` | Derived | Gauge panel, banners, table backgrounds |
| Surface alt | `#EEF2F4` | Derived | Secondary track/progress bars |
| Border | `rgba(20,24,27,0.08)` | Derived | Hairline dividers |
| Border (strong) | `rgba(20,24,27,0.14)` | Derived | Card outlines |

### Severity / status colors

| Token | Value | Status | Used for |
|---|---|---|---|
| High severity | `#C97A1E` (amber) | Derived | "High" issue badges |
| Medium severity | `#3E7C90` (steel blue) | Derived | "Medium" issue badges |
| Low severity | `#6B7268` (muted sage) | Derived | "Low" issue badges |
| Excellent status | `#2F8F57` (green) | Derived | Model Health = Excellent |
| Good status | `#5C8A3A` (olive green) | Derived | Model Health = Good |
| Fair status | `#C97A1E` (amber) | Derived | Model Health = Fair |
| Critical status | `#D64545` / `#C0392B` | Derived | Model Health = Critical |

> None of the severity/status colors exist on tridant.com's marketing site
> (it has no error states, alert banners, or severity badges to sample), so
> these are my own choices, kept in the same tonal family as the measured
> brand colors. Swap any of these freely if Tridant has an internal style
> guide with defined semantic colors.

---

## Typography

| Token | Value | Status |
|---|---|---|
| Font family | **Source Sans Pro** | **Measured** — confirmed via `font-family` and rendered font `SourceSansPro-SemiBold` on the CTA button |
| Body weight | 400 (Regular) | Measured (standard body text) |
| Emphasis/heading weight | 600 (SemiBold) | **Measured** — exact weight used on the CTA button |
| Loaded from | Google Fonts (`fonts.googleapis.com`) | — |
| Weights loaded in-app | 400, 600, 700 | 700 added for larger headline sizes, not separately confirmed on their site |

---

## Shape & elevation

| Token | Value | Status |
|---|---|---|
| Border radius | `4px` | **Measured** — CTA button `border-radius` |
| Shadow (cards) | `0 12px 30px -16px rgba(20,24,27,0.16)` | Derived — soft elevation for a light theme |

---

## Logo

| Property | Detail |
|---|---|
| Source file | Uploaded by you — black "TRIDANT" wordmark, 535×123px, solid white background, no transparency |
| Processing applied | Converted white background to true transparency using luminance-based alpha grading (not a hard cutout — edges stay anti-aliased/smooth); wordmark recolored to pure black; image trimmed tight to content bounding box |
| Final asset size | 483×85px |
| Color kept | Black (`#000000`) — contrast-checked against the `#9C66A0` header: black = **4.82:1**, white = **4.36:1**, so black reads slightly better |
| Storage | Embedded inline as base64 in `app.py` (`TRIDANT_LOGO_B64` constant, ~6.3KB) — not an external file link, so it can never break inside the sandboxed report iframe |
| Display size in header | 28px height, width auto |
| Separate asset | Saved alongside this document as `tridant_logo_transparent.png` for reuse elsewhere (slides, docs, etc.) |

---

## Where each token is applied

| Surface | What's themed |
|---|---|
| `.streamlit/config.toml` | Native Streamlit chrome: `primaryColor` (accent), background, sidebar background, body text |
| CSS injection in `app.py` (top of file) | Font import, button styling, active-tab color, `stHeader` background (`#9C66A0`) |
| Executive Summary HTML template (`EXEC_TEMPLATE` in `app.py`) | Full light-theme design system — header bar, KPI tiles, gauge, findings table, severity badges, footer |

---

## Open items / things to confirm with Tridant directly

- **Heading color** (`#2B2E31`) — not separately measured; only body text (`#5A5A5A`) was confirmed. If Tridant's actual `h1`/`h2` color differs, send it over.
- **Severity/status colors** — entirely derived, since the marketing site has no equivalents. Fine to leave as-is or replace with an internal style guide's semantic colors if one exists.
- **Header purple `#9C66A0`** — this was given by you, not found on tridant.com itself; confirm it's the intended source (secondary brand color, a specific campaign color, etc.) if it needs to match something exactly elsewhere.
