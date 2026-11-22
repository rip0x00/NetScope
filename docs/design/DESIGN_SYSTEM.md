# Design System

NetScope's interface is an engineering tool: calm, dense where density helps,
and quiet. Every visual element exists because it carries information or an
action. The machine-readable form of this document is
`assets/branding/tokens.json`; if the two disagree, tokens.json is corrected
to match this document.

## Colour

### Dark theme

| Role | Hex | Contrast on `#101419` | Use |
|---|---|---|---|
| Background | `#101419` | — | Window background |
| Background, secondary | `#151B22` | — | Sidebars, inset areas |
| Surface | `#1B232C` | — | Panels, tables |
| Surface, elevated | `#222C37` | — | Menus, dialogs, popovers |
| Border | `#303B47` | — | Dividers, panel edges |
| Text | `#EDF2F7` | 16.41 : 1 | Primary text |
| Text, secondary | `#9AA8B7` | 7.62 : 1 | Labels, secondary values |
| Text, muted | `#687787` | 4.03 : 1 | Non-essential annotations only; never body text or values |
| Accent | `#3987D8` | 4.96 : 1 | Primary actions, selection, links |
| Accent, secondary | `#36A7B8` | 6.49 : 1 | Secondary highlights, the brand dot |
| Success | `#36A879` | 6.19 : 1 | Passing states |
| Warning | `#D69A42` | 7.53 : 1 | Degraded states |
| Error | `#D65B61` | 4.87 : 1 | Failed states |

### Light theme

The light theme is designed on its own surfaces, not inverted from dark.
Surfaces are white and near-white; the brand accents are darkened because the
dark-theme accent values do not reach readable contrast on light surfaces
(`#3987D8` measures 3.73 : 1 on white, `#36A7B8` only 2.85 : 1). Semantic
meaning is identical across themes; only the values change.

| Role | Hex | Contrast on `#F7F9FB` | Contrast on `#FFFFFF` |
|---|---|---|---|
| Background | `#F7F9FB` | — | — |
| Background, secondary | `#EDF1F5` | — | — |
| Surface | `#FFFFFF` | — | — |
| Surface, elevated | `#FFFFFF` (separated by border and shadow) | — | — |
| Border | `#D5DEE7` | — | — |
| Text | `#14202B` | 15.65 : 1 | 16.52 : 1 |
| Text, secondary | `#43556A` | 7.25 : 1 | 7.65 : 1 |
| Text, muted | `#66788C` | 4.30 : 1 | 4.54 : 1 |
| Accent | `#2F6FB3` | 4.92 : 1 | 5.19 : 1 |
| Accent, secondary | `#22707E` | 5.40 : 1 | 5.70 : 1 |
| Success | `#1F7A54` | 5.01 : 1 | 5.29 : 1 |
| Warning | `#9A6414` | 4.73 : 1 | 4.99 : 1 |
| Error | `#B23A42` | 5.56 : 1 | 5.87 : 1 |

Contrast ratios were computed with the WCAG relative-luminance formula.
Muted text sits below the 4.5 : 1 body-text threshold in both themes by
design: it is restricted to short, non-essential annotations, and any value a
user needs to act on is rendered in secondary text or above.

Status is never carried by colour alone: every state also has a text label
and, in tables, a position in a fixed status column.

## Typography

- UI typeface: **Inter**. Fallbacks: `-apple-system`, `Segoe UI`, sans-serif.
- Measurements, addresses, and tabular data: **JetBrains Mono**, or tabular
  figures where the platform font provides them. Numbers that are compared
  vertically must align vertically.

| Style | Size | Weight | Line height | Use |
|---|---|---|---|---|
| Display | 28 px | 600 | 36 px | The single primary figure of a view, when one exists |
| Title | 20 px | 600 | 28 px | View titles |
| Subtitle | 16 px | 600 | 24 px | Section headings |
| Body strong | 14 px | 600 | 22 px | Labels, table headers |
| Body | 14 px | 400 | 22 px | Default text |
| Caption | 12 px | 400 | 20 px | Annotations, timestamps |

Text scales with the platform's dynamic-type setting; layouts must survive
200% scaling without clipping values.

## Spacing and shape

- Spacing scale on a 4 px base: **4, 8, 12, 16, 24, 32, 48**. No other
  spacing values in components.
- Corner radii are restrained: **4 px** (inputs, chips), **6 px** (panels),
  **8 px** (dialogs, the app-icon tile proportion). No pill shapes except
  status indicators that are genuinely pill-shaped data (for example a
  latency sparkline badge is not one — do not make it one).
- Borders separate surfaces before shadows do. Shadows are reserved for
  genuinely floating elements (menus, dialogs).

## Iconography

- Baseline set: **Lucide** SVG icons, 24 px grid, 1.5 px stroke, round caps
  only where Lucide itself uses them. One icon family per surface; never mix
  filled and outline styles in one view.
- Custom NetScope icons follow the same grid and stroke weight and are drawn
  for concepts Lucide does not cover (the brand mark in `assets/branding/`
  is the reference for stroke behaviour).
- Icons never stand alone for an action a first-time user must discover:
  pair with a text label or a tooltip.
- No emoji anywhere in the interface. No unicode symbols as substitute icons.

## Motion

- Motion communicates a state change or it does not ship.
- Durations: 120 ms for small state changes, 200 ms for view transitions.
  Nothing longer, nothing looping for decoration.
- Charts update by drawing new data, not by animating transitions between
  values.
- When the platform reports a reduced-motion preference, transitions are
  removed, not shortened.

## Accessibility

- Visible focus indicator on every interactive element: a 2 px accent
  outline, offset by 2 px, never removed for appearance.
- Full keyboard operation of every view; logical tab order that follows the
  visual order.
- Touch targets at least 44 × 44 px on mobile, 32 px minimum height for
  desktop controls.
- Body text meets WCAG AA contrast (4.5 : 1) in both themes; the muted-text
  exception above is documented and bounded.
- Screen-reader labels on all icon-bearing controls and on every chart
  (charts also expose their data as a table or a text summary).
- RTL layouts mirror navigation and reading order; numeric columns and
  charts keep their data direction and are labelled accordingly.

## Brand mark

The mark is a measurement reticle: four ticks at the cardinal points crossing
a thin ring, with a centre point — an aperture drawn on a strict 48-unit
grid, single stroke weight (3 units), flat colour, no gradients. It reads as
an instrument reticle, not as a network diagram. Files in
`assets/branding/`:

- `logo-primary.svg` — symbol and wordmark, for light surfaces.
- `logo-compact.svg` — reduced wordmark size for narrow headers.
- `logo-symbol.svg` — the mark alone.
- `logo-mono-dark.svg` / `logo-mono-light.svg` — single-colour versions for
  dark and light surfaces respectively.
- `app-icon.svg` — the mark centred on a `#101419` rounded tile.
- `favicon.svg` — simplified mark (ring removed, stroke raised) for 16 px.

Platforms take the mark from this directory. No module redraws it.
