# Screening Workbench v1 — visual direction 01: Field Notes

**Status:** owner-authorized visual direction for initial implementation. This is an original project decision, not a substitute for a pre-existing external brand guide. **Primary surface:** Operate. Screening and review queues are work surfaces; density, keyboard focus, and clear decision state take priority over marketing composition.

## Design intent

Make Screening Workbench feel like a careful research instrument: calm, legible, paper-adjacent without imitating a notebook or any incumbent interface. Use a restrained mineral palette with one deep evergreen action color, clear warm/cool status distinction, and a compact editorial heading. Treat the citation as the central object; keep chrome quiet and actions explicit.

## Tokens

```css
:root {
  color-scheme: light;
  --canvas: #f5f6f2;
  --surface: #ffffff;
  --surface-raised: #fbfcf9;
  --ink: #1f2a25;
  --muted: #66736b;
  --line: #dce3dc;
  --line-strong: #bdc9bf;
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
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --shadow-float: 0 12px 32px rgb(28 44 35 / 0.12);
  --font-ui: "Segoe UI", "Aptos", system-ui, sans-serif;
  --font-reading: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  --font-mono: "Cascadia Code", Consolas, monospace;
}
```

## Use rules

- Use a light neutral page canvas; reserve white for record surfaces and dialogs.
- Use evergreen for primary confirm/action buttons and active navigation, not decorative rails.
- Set article titles in the reading serif, with UI labels and metadata in the UI sans. On a machine without Iowan Old Style installed, `Palatino Linotype` (next in the stack) is an accepted substitute, not a theme deviation.
- Use semantic include/maybe/exclude text labels with distinct colors; never rely on color alone. The `-soft`/`-border` tints exist specifically for decision-button and info-callout fills (text/icon stays the full-strength semantic color on top).
- Keep keyboard focus conspicuous (`--focus`, 2px outline, offset). Do not suppress browser focus without an accessible replacement.
- Keep controls >=40px high; critical one-key shortcuts remain visible in a compact key legend.
- Use compact 8px spacing rhythm, 6px control radius, 10px cards, and 14px dialogs. Avoid pill-shaped buttons and excessive cards.
- Decision actions should be adjacent and evenly reachable; destructive or irreversible actions require a clear confirmation.
- Motion is limited to short 120–180ms state transitions and respects reduced-motion preference.
- Charts and PRISMA exports use high-contrast neutral strokes plus text labels; remain legible in grayscale and print.
- No gradient backgrounds, glass effects, illustration filler, or arbitrary headline statistics.

## Accessibility gates

- Body and metadata text meet WCAG AA contrast; ensure all state colors are paired with text or icon+text.
- Selection, conflict, stale model, error, and success states are announced semantically.
- At 200% zoom, screening controls and record text remain usable with no horizontal page-level overflow.
- Support Windows high contrast/forced colors and reduced motion.

## Implementation note

This is an approved first-pass visual system for Screening Workbench, chosen after the owner authorized a new theme. It may evolve as real screens are implemented, but any change must preserve accessibility and the independent identity rule. Do not claim it is an existing external design system.

**2026-10-07:** Added `-soft`/`-border` decision-button and info-callout tints (derived tints of the existing `--include`/`--maybe`/`--exclude`/`--info` tokens, not new hues) per the Screening-tab UI reference target — see `docs/ui-reference-screening.md`.
