# Screening Workbench — visual direction 02: Card Catalogue

**Status:** owner-authorized on 2026-10-21 as the successor to direction 01 (Field Notes). It is an original project decision, not a substitute for a pre-existing Klaro brand guide. **Primary surface:** Operate. Screening and review queues are work surfaces; density, keyboard focus, and clear decision state take priority over marketing composition.

## Design intent

Make Screening Workbench feel like a careful research instrument built around the citation, the way a library card catalogue is. The project is the **drawer**: deep catalogue evergreen frames the window (menus, header, section rail, status bar) and is the dominant color. The record is the **card**: warm card-stock surfaces carry the content. One sharp **highlighter** accent marks what the reviewer is looking at now. The include/maybe/exclude triad from direction 01 is unchanged.

Direction 01's calm, legible, paper-adjacent intent still applies. What changes is commitment: one dominant color instead of evenly distributed tints, bundled typefaces instead of whatever the machine has installed, and the record as the one raised object.

## Tokens

```css
:root {
  color-scheme: light;
  /* drawer: window chrome */
  --drawer: #1d3a32;
  --drawer-raised: #28493f;
  --drawer-ink: #f2f0e6;
  --drawer-muted: #a9bfb4;
  /* highlighter: "now" and "needs you" only */
  --signal: #e8d44d;
  --signal-soft: #f7efb5;
  /* desk and card */
  --canvas: #dce2d9;
  --surface: #fffefa;
  --surface-raised: #fbfcf9;
  --ink: #1f2a25;
  --muted: #55625a;
  --line: #cbd5cb;
  --line-strong: #bdc9bf;
  /* action and state (unchanged from direction 01) */
  --accent: #23634d;
  --accent-hover: #1c513f;
  --accent-soft: #e7f0eb;
  --include: #276149;
  --maybe: #80540f;
  --exclude: #a4443e;
  --info: #3d6476;
  --focus: #c45a32;
  --include-soft: #e8f1ec;
  --maybe-soft: #f6eedf;
  --exclude-soft: #f7e8e6;
  --info-soft: #e6eef1;
  --include-border: #a9c8b6;
  --maybe-border: #dcc39a;
  --exclude-border: #dfb0ab;
  --grid-minor: #eef1ea;
  --grid-major: #dfe5dc;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --font-ui: "Atkinson Hyperlegible Next", "Segoe UI", "Aptos", sans-serif;
  --font-reading: "Newsreader 16pt", "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  --font-title: "Newsreader 16pt Medium", "Newsreader 16pt", "Palatino Linotype", serif;
  --font-mono: "Atkinson Hyperlegible Mono", "Cascadia Code", Consolas, monospace;
}
```

`theme.TOKENS` in `src/screening_workbench/theme.py` is the source of truth; this block mirrors it.

## Night Stacks (dark palette)

The catalogue room after hours: the same roles, structure and rules as Card Catalogue, with every token redefined for a dark room. The drawer stays deep evergreen and the highlighter stays yellow; desk and card go dark; semantic colors lift to pastel so they keep >= 4.5:1 on the dark card.

**Choosing a theme.** View > Theme offers Match Windows (default), Card Catalogue (light) and Night Stacks (dark). The palette is read once at start-up, in this order: the `SW_THEME` environment variable, the saved View > Theme choice, then Windows' app light/dark mode. A new choice applies on the next start, because Tk widgets take their colors when they are built. The choice is saved to a local settings file (`%APPDATA%\Screening Workbench\settings.json`, or `SW_SETTINGS_PATH`). In Night Stacks the app asks Windows for a dark title bar.

**Role tokens.** Four roles differ between palettes even though their light values repeat another token: `on_signal` (text on the highlighter), `inverse_bg`/`inverse_fg` (the header's Export button), and `rule_ink` (the call-number rule's progress segment). The `control*` and `trough` tokens name clam's neutral control colors so they can be redefined for the dark room; their light values are clam's own defaults, and every ttk state map (disabled, hover, pressed) is routed through them.

**Gates.** Every pair in `theme._CONTRAST_TOKEN_PAIRS` is asserted >= 4.5:1 for both palettes at import (`PALETTE_CONTRAST`). A test walks every widget in both palettes, in normal, disabled, hover and pressed states, and fails on any color that is not a palette token. Exports (PRISMA SVG, CSVs) are theme-independent and stay print-ready. Windows high contrast still overrides decoration (graph paper) in either palette.

| Token | Card Catalogue | Night Stacks |
|---|---|---|
| `drawer` | `#1d3a32` | `#0f221c` |
| `drawer_raised` | `#28493f` | `#1d3a32` |
| `drawer_ink` | `#f2f0e6` | `#f2f0e6` |
| `drawer_muted` | `#a9bfb4` | `#9fb5aa` |
| `signal` | `#e8d44d` | `#e8d44d` |
| `signal_soft` | `#f7efb5` | `#4a4521` |
| `canvas` | `#dce2d9` | `#141b18` |
| `surface` | `#fffefa` | `#1d2622` |
| `surface_raised` | `#fbfcf9` | `#242f2a` |
| `ink` | `#1f2a25` | `#e4eae3` |
| `muted` | `#55625a` | `#a2b1a8` |
| `line` | `#cbd5cb` | `#34423b` |
| `line_strong` | `#bdc9bf` | `#4b5c53` |
| `accent` | `#23634d` | `#74c7a3` |
| `accent_hover` | `#1c513f` | `#8fd5b6` |
| `accent_soft` | `#e7f0eb` | `#22392f` |
| `accent_focus` | `#174b39` | `#a7e0c6` |
| `include` | `#276149` | `#7fcb9f` |
| `maybe` | `#80540f` | `#e3b65f` |
| `exclude` | `#a4443e` | `#f1918a` |
| `info` | `#3d6476` | `#90c0d6` |
| `focus` | `#c45a32` | `#f0905c` |
| `include_soft` | `#e8f1ec` | `#1e3328` |
| `maybe_soft` | `#f6eedf` | `#382e18` |
| `exclude_soft` | `#f7e8e6` | `#3b2523` |
| `info_soft` | `#e6eef1` | `#1d2f37` |
| `include_border` | `#a9c8b6` | `#3f6b52` |
| `maybe_border` | `#dcc39a` | `#7a5f2a` |
| `exclude_border` | `#dfb0ab` | `#7f4640` |
| `grid_minor` | `#eef1ea` | `#212b27` |
| `grid_major` | `#dfe5dc` | `#2a3631` |
| `on_signal` | `#1f2a25` | `#1b1d10` |
| `inverse_bg` | `#fffefa` | `#f2f0e6` |
| `inverse_fg` | `#1d3a32` | `#0f221c` |
| `rule_ink` | `#1d3a32` | `#74c7a3` |
| `control` | `#dcdad5` | `#2c3833` |
| `control_light` | `#eeebe7` | `#36443e` |
| `control_dark` | `#cfcdc8` | `#222c28` |
| `control_border` | `#9e9a91` | `#4b5c53` |
| `trough` | `#bab5ab` | `#1a221f` |

## Typography

The three families are bundled under `src/screening_workbench/fonts/` (SIL OFL 1.1, unmodified static cuts; provenance in `docs/license-audit.md`) and loaded for the app process only with `AddFontResourceExW(..., FR_PRIVATE)` before Tk starts. Nothing is installed on the user's machine. If loading fails, each stack falls back to the direction 01 fonts.

| Role | Face | Tk size |
|---|---|---|
| Wordmark | Newsreader 16pt Medium | 17 |
| Record titles (all tabs) | Newsreader 16pt Medium | 15–16 |
| Abstracts and excerpts | Newsreader 16pt | 11–12 |
| UI, labels, metadata | Atkinson Hyperlegible Next | 9–10, bold for emphasis |
| IDs, call numbers, keys, counts | Atkinson Hyperlegible Mono | 9 |

Atkinson Hyperlegible was drawn for low-vision legibility, with distinct `I`/`l`/`1` and `O`/`0`; that matters in a keyboard-first tool where `I` means Include. Tk cannot letter-space, so avoid all-caps micro-labels in new work; use sentence-case bold 9 in `--muted`.

## Use rules

- The drawer frames the window. Do not use drawer colors inside the work area.
- Use `--canvas` for the desk; reserve `--surface` for cards, record surfaces and dialogs. Widgets placed on a card paint the card surface (`theme.match_surface_backgrounds`).
- The record is the one raised object on the Screening tab. Queue and support columns sit flat on the desk.
- `--signal` marks "now" (active section, current queue row, search hits in the abstract) and "needs you" (nonzero Conflicts and Duplicates counts). It never encodes a decision and is never text color. Text on it is `--ink`.
- Use evergreen (`--accent`) for primary confirm/action buttons inside the work area. The header's primary action is an inverse button (card fill, drawer text) because evergreen on the drawer would vanish.
- Use semantic include/maybe/exclude text labels with distinct colors; never rely on color alone. The `-soft`/`-border` tints exist for decision-button and info-callout fills. Nothing outside the decision triad borrows these colors (the blind-mode chip included).
- Keep keyboard focus conspicuous (`--focus`, 2–3px outline). Do not suppress focus without an accessible replacement.
- Keep controls >=40px high; critical one-key shortcuts remain visible in a compact key legend.
- Use compact 8px spacing rhythm, 6px control radius, 10px cards, and 14px dialogs. Avoid pill-shaped buttons and nested cards.
- Decision actions should be adjacent, equal in width, and evenly reachable; destructive or irreversible actions require a clear confirmation.
- Decision buttons show their key as a mono keycap beside the word (built from labels, so it scales with the font). While an Exclude waits for its reason, the reason list is tinted `--exclude-soft`, its keys take the exclude hue, and the Exclude button carries the focus ring.
- Motion is limited to short 120–180ms state transitions and respects reduced-motion preference. Reduced motion follows, in order, the saved View > Reduce motion choice, `SW_REDUCE_MOTION`, and Windows' "Show animations" setting (`display_prefs`). The View choice applies immediately and persists in local settings.
- The one orchestrated moment is the decision stamp: a 170 ms date-due stamp over the record card, drawn only after the vote is saved. Any key, click or refresh during it first finishes that advance, so a decision always lands on the record on screen. The call-number rule eases to its new length in ~140 ms.
- Charts and PRISMA exports use high-contrast neutral strokes plus text labels; remain legible in grayscale and print.
- No gradient backgrounds, glass effects, illustration filler, or arbitrary headline statistics.
- The PRISMA live preview sits on graph paper (`--grid-minor` every 8px, `--grid-major` every 40px) behind every box and label. It is skipped in Windows high contrast and never drawn in the exported SVG.

## Accessibility gates

- Body and metadata text meet WCAG AA contrast; every text pair the UI uses is asserted at import in `theme._CONTRAST_TOKEN_PAIRS` (>= 4.5:1), including the drawer and highlighter pairs.
- Ensure all state colors are paired with text or icon+text.
- Selection, conflict, stale model, error, and success states are announced semantically.
- At 200% zoom, screening controls and record text remain usable with no horizontal page-level overflow.
- Support Windows high contrast/forced colors and reduced motion.

## Implementation note

Direction 02 evolves direction 01 and keeps its accessibility gates and independent identity rule. Do not claim it is an existing Klaro design system.

**2026-10-07 (direction 01):** Added `-soft`/`-border` decision-button and info-callout tints per the Screening-tab UI reference target — see `docs/ui-reference-screening.md`.

**2026-10-21 (direction 02):** Owner authorized the Card Catalogue direction from the 1.0.0 aesthetics review. Landed in three parts: bundled typefaces (R1), drawer palette and chrome (R2), and the record card on the Screening tab (R3). The decision stamp and reduced-motion probe (R4), desk dot grid and PRISMA graph paper (R5) are approved directions not yet implemented.

**2026-10-21 (direction 02, R3 finished):** keycap decision buttons and the armed reason list landed. The status-bar shortcut legend is kept on purpose: Duplicates and PRISMA have no other shortcut hint.

**2026-10-21 (direction 02, Phase C):** R4 decision stamp, reduced-motion probe and toggle, and the progress tween landed; R5 PRISMA graph paper landed. Two proposals were not built: the one-time drawer reveal on project open (deferred until the stamp has been used in a real screening session, as the review planned), and the desk dot grid. The dot grid would only show where the canvas itself is visible, and in Tk every container frame, label and checkbox on the desk paints its own opaque background, so the pattern would break into flat patches around text and controls. It needs the work area rebuilt on a Canvas, which is out of proportion to its value.

**2026-10-21 (direction 02, v2):** Night Stacks dark palette and View > Theme landed. The open-project drawer reveal remains deferred until after a real screening session.
