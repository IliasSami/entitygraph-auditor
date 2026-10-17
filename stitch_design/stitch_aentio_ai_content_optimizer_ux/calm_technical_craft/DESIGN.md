---
name: Calm Technical Craft
colors:
  surface: '#FFFFFF'
  surface-dim: '#e0d8d5'
  surface-bright: '#fff8f5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#faf2ee'
  surface-container: '#f4ece8'
  surface-container-high: '#eee7e3'
  surface-container-highest: '#e9e1dd'
  on-surface: '#1e1b19'
  on-surface-variant: '#464554'
  inverse-surface: '#33302d'
  inverse-on-surface: '#f7efeb'
  outline: '#777586'
  outline-variant: '#c7c4d7'
  surface-tint: '#5148d7'
  primary: '#2a14b4'
  on-primary: '#ffffff'
  primary-container: '#4338ca'
  on-primary-container: '#c1beff'
  inverse-primary: '#c3c0ff'
  secondary: '#1d4ed8'
  on-secondary: '#ffffff'
  secondary-container: '#4069f2'
  on-secondary-container: '#fffbff'
  tertiary: '#00451c'
  on-tertiary: '#ffffff'
  tertiary-container: '#005f29'
  on-tertiary-container: '#78da8b'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e3dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#100069'
  on-primary-fixed-variant: '#372abf'
  secondary-fixed: '#dce1ff'
  secondary-fixed-dim: '#b7c4ff'
  on-secondary-fixed: '#001551'
  on-secondary-fixed-variant: '#0039b5'
  tertiary-fixed: '#95f8a7'
  tertiary-fixed-dim: '#79db8d'
  on-tertiary-fixed: '#00210a'
  on-tertiary-fixed-variant: '#005323'
  background: '#fff8f5'
  on-background: '#1e1b19'
  surface-variant: '#e9e1dd'
  background-canvas: '#FAFAF9'
  surface-subtle: '#F5F5F4'
  border-hairline: '#E7E5E4'
  text-muted: '#78716C'
  primary-hover: '#3730A3'
  primary-soft: '#EEF2FF'
  success-soft: '#F0FDF4'
  warning: '#B45309'
  warning-soft: '#FFFBEB'
  danger: '#B91C1C'
  danger-soft: '#FEF2F2'
  info-soft: '#EFF6FF'
  dark-background: '#0C0C0E'
  dark-surface: '#16161A'
  dark-border: '#27272A'
  dark-text: '#FAFAFA'
  dark-text-muted: '#A1A1AA'
  dark-primary: '#818CF8'
typography:
  display-h1:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
  display-h1-mobile:
    fontFamily: Inter
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 32px
  section-h2:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  subsection-h3:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-large:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-medium:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-small:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-medium:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
  editor-prose:
    fontFamily: Source Serif 4
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 30px
  code-data:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system serves a technical, self-hosted content and entity optimization platform. The product experience balances the quiet, distraction-free environment of a long-form writing desk with the surgical precision of an enterprise developer tool. 

The aesthetic adheres to **Quiet Minimalism** paired with high-craft utilitarian SaaS patterns (inspired by Linear, Notion, and Raycast). The interface minimizes cognitive load by rejecting synthetic gamification, saturated background fills, and aggressive decorative shadows. Instead, it relies on crisp 1px hairline structural boundaries, strict proportional typography, generous whitespace around prose, and compact density in data-heavy sidebars.

The emotional tone is calm, analytical, and authoritative. Users should feel complete mastery over complex semantic schemas, knowledge graphs, and AI-driven recommendations without visual noise or algorithmic anxiety.

## Colors

The palette is engineered around subtle stone neutrals and focused, low-vibrancy semantic signals. The dominant canvas background uses warm stone (`#FAFAF9`), separating elevated work surfaces (`#FFFFFF`) with 1px hairline neutral borders (`#E7E5E4`).

Interactive dominance belongs to Deep Indigo (`#4338CA`), reserved for primary actions, focus rings, and confirmed diff modifications. Secondary entity claims rely on Blue (`#1D4ED8`), while operational health and status indicators use Green (`#15803D`), Amber (`#B45309`), and Crimson Red (`#B91C1C`).

Each accent color is paired with a high-luminance "soft" tint (`primary-soft`, `success-soft`, etc.) used strictly for badge containers, subtle callout backgrounds, and inline revision diff tracking. 

In Dark Mode, the background shifts to deep neutral zinc (`#0C0C0E`) with surfaces at `#16161A` and borders at `#27272A`. All status accents lift by exactly one lightness tier to preserve contrast ratios across dark surfaces.

## Typography

The design system employs a purposeful three-tier font hierarchy:

1. **System & App UI (`Inter`):** Powers application headers, controls, sidebars, tables, and inspection panels. Compact sizes (13px and 14px) maintain clarity in dense side panels.
2. **Editorial Canvas (`Source Serif 4`):** Powers the distraction-free central drafting viewport. Set at 18px with a 1.65 line-height ratio (~30px), this serif provides an immersive reading rhythm for long-form content and structural review.
3. **Machine Data & Schemas (`JetBrains Mono`):** Applied to JSON-LD graphs, entity URIs, Wikidata IDs, and raw model parameter readouts at 13px.

### Numerics & Accessibility Rules
- All tabular data, metrics, entity match percentages, and word counts must declare `font-variant-numeric: tabular-nums` to prevent horizontal jitter during live edits.
- Inline signals must not rely solely on color. When denoting textual anomalies within prose, style decorations must be coupled with gutter markers:
  - **Ambiguous Entity:** Amber dashed underline (`◆` in gutter).
  - **Claim Needing Source:** Blue dotted underline (`§` in gutter).
  - **Factual Contradiction:** Red dotted underline (`§` in gutter).
  - **Verified Assertion:** Solid 2px left border bar (`✓` in gutter).
  - **Vague / Filler Copy:** Red wavy underline (`!` in gutter).

## Layout & Spacing

Layout geometry follows an exact **8px spatial grid**. Density is calibrated for data-dense productivity tools:

### Workspace Multi-Pane Distribution
- **Left Navigation Rail:** `240px` static width; collapses to a `56px` icon rail on screens below 1280px.
- **Context / Filter Drawer:** `280px` collapsible side pane.
- **Center Editorial Viewport:** Fluid space with an enforced maximum line-length width of `720px` to maintain optimal typographic measure.
- **Right Intelligence Inspector:** `380px` desktop panel (condensable to `360px`). Transforms into an overlay drawer at viewport widths below `1024px`.
- **Entity Hub Slide-over:** Fixed `420px` overlay panel.

### Breakpoints & Reflow
- **≥ 1440px (Wide Desktop):** Simultaneous display of Left Context, Center Editor (720px max), and Right Inspector.
- **1280px (Standard Desktop):** Left context panel drops into collapsed 56px mode.
- **1024px (Tablet / Small Display):** Right Intelligence panel transitions into a toggled modal drawer.
- **≤ 640px (Mobile):** Linearized single-column view strictly optimized for quick reviews and recommendations.

## Elevation & Depth

This system avoids heavy, blurred drop shadows. Depth and visual hierarchy are communicated almost entirely through **tonal separation** and **1px structural hairline borders** (`#E7E5E4` in light mode, `#27272A` in dark mode).

### Surface Layers
1. **Canvas Layer (Base, z-0):** `#FAFAF9`. The foundation across wide panes.
2. **Surface Layer (Workspace, z-10):** `#FFFFFF`. The editing canvas, table rows, and active inspector containers.
3. **Subtle Surface (Recessed, z-0):** `#F5F5F4`. Used for read-only metadata groups, code display blocks, and inactive tabs.

### Elevated & Floating Elements
Soft ambient shadows are permitted only for floating contextual tools to differentiate them from the flat editing surface:
- **Floating Format Bar / Action Popovers:** `box-shadow: 0 4px 12px rgba(28, 25, 23, 0.06), 0 1px 2px rgba(28, 25, 23, 0.04)`.
- **Command Palette (`⌘K`) & Slide-over Drawers:** `box-shadow: 0 12px 32px rgba(28, 25, 23, 0.08), 0 2px 6px rgba(28, 25, 23, 0.04)`.
- **Z-Index Scale:** Canvas (`0`), Floating Toolbars (`100`), Side Drawers (`200`), Global Modals & Palette (`300`).

## Shapes

The interface balances sharp technical utility with soft ergonomic contours:

- **Cards & Structured Inspection Panels:** Enforce a `12px` corner radius (`rounded-lg`), grounding larger analytical units.
- **Form Controls & Interactive Buttons:** Enforce an `8px` corner radius (`rounded`), creating tight, functional interactive targets.
- **Status Pills, Badges & Entity Chips:** Enforce fully rounded pill bounds (`9999px` / `rounded-full`).

Focus states demand a crisp `2px` solid primary ring (`#4338CA`) offset by `2px` white space to ensure unambiguous focus distinction across keyboard-centric navigation.

## Components

### Buttons & Interactive Controls
- **Primary:** Background `#4338CA`, text `#FFFFFF`, radius `8px`. Hover state: `#3730A3`. Active height: `36px` (regular) or `32px` (compact data views).
- **Secondary / Ghost:** Transparent or `#FFFFFF` background with a 1px `#E7E5E4` border, text `#1C1917`. Hover state: `#F5F5F4`.
- **Destructive:** Background `#B91C1C`, text `#FFFFFF`. Hover state: `#991B1B`. Soft variant: `#FEF2F2` background with `#B91C1C` text.

### Pills, Badges & Entity Chips
- Fully rounded (`9999px`), height `22px` to `24px`, font size `13px` (`JetBrains Mono` or `Inter Medium`).
- Status variants:
  - **Healthy / Optimal:** Background `#F0FDF4`, text `#15803D`.
  - **Review Needed:** Background `#FFFBEB`, text `#B45309`.
  - **Critical Conflict:** Background `#FEF2F2`, text `#B91C1C`.
  - **Entity Claim:** Background `#EFF6FF`, text `#1D4ED8`.

### Input Fields & Controls
- **Inputs & Selects:** Height `36px` (`32px` in compact toolbars), background `#FFFFFF`, border 1px `#E7E5E4`, radius `8px`, typography `14px Inter`.
- **Checkboxes & Radios:** `16px` bounds, radius `4px` (checkbox) or circular (radio), border 1px `#E7E5E4`. When checked: fill `#4338CA`, border `#4338CA`.

### Cards & Inspector Panels
- Container surfaces use `#FFFFFF` on `#FAFAF9` canvas, bound by 1px hairline `#E7E5E4` and `12px` corner radii.
- Headers within cards use `14px` Semibold Inter with a subtle bottom divider border. Card bodies use `12px` or `16px` padding depending on density mode.

### Git-Style Text Diff Markers
- Suggestions generated by AI optimization agents are displayed inline like Git diff hunks:
  - **Insertions:** Background `#EEF2FF`, underline solid `#4338CA`. Inline acceptance widget accompanies the change.
  - **Deletions:** Text strikethrough with `#B91C1C` line and color.
  - **Floating Action Deck:** Mini confirmation toolbar hovering over changed blocks offering quick `Accept (Y)` or `Reject (N)` keyboard shortcuts.

### Iconography
- Icons are rendered via 1.5px stroke Lucide-style line assets bounded strictly within `16px × 16px` frames. Icons serve informative purposes directly adjacent to actionable text or entity state tags.