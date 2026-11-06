# KnowFlow design system

Source: [DRD](DRD.md). Implementation: `apps/web/src/app/globals.css` is the only place colours, radii and
fonts are defined. Components read them through Tailwind/shadcn tokens. `src/lib/tokens.test.ts`
verifies the values and contrast ratios.

## Colour tokens (DRD §2)

| Token | CSS variable | Value | Tailwind | Use |
|---|---|---|---|---|
| Canvas | `--kf-canvas` | `#F6F5F1` | `bg-background` | App background |
| Surface | `--kf-surface` | `#FFFFFF` | `bg-card`, `bg-surface` | Cards, panels, sidebar |
| Ink | `--kf-ink` | `#202B33` | `text-foreground` | Text, headings, status labels |
| Secondary text | `--kf-ink-secondary` | `#65717A` | `text-muted-foreground` | Metadata, helper text |
| Deep teal | `--kf-teal` | `#245B57` | `bg-primary`, `text-primary`, `ring` | Primary actions, active nav, links, focus |
| Accent tint | `--kf-teal-tint` | `#E8F0ED` | `bg-accent` | Active/selected background |
| Border | `--kf-border` | `#E3E6E3` | `border` | Dividers, inputs |
| Success / Warning / Danger / Info | `--kf-success` … | `#287A55` `#A66A1F` `#B54742` `#496D8C` | `text-success` … | Status **icons** only |
| Fill (derived) | `--kf-fill` | `#EFEEE9` | `bg-secondary`, `bg-muted` | Hover and fill surfaces. Not a DRD token |

There's no dark theme yet (DRD §2: only after light mode is complete), and no gradients anywhere. The token test checks both.

### Measured contrast (WCAG 2.2) and resulting rules

| Foreground | on Surface | on Canvas | on Tint/Fill |
|---|---|---|---|
| Ink | 14.44 | 13.23 | 12.4 |
| Secondary text | 5.00 | 4.59 | **4.3 (fails AA text)** |
| Teal | 7.75 | 7.11 | 6.69 |
| Warning | **4.47 (fails AA text)** | **4.09** | 3.85 |
| Success / Danger / Info | ≥ 5.2 | ≥ 4.8 | ≥ 4.5 |

Rules that follow from these measurements:

1. **Status colour is for icons only.** Icons need 3:1, and every status colour passes on every surface. Status labels are rendered in Ink (see `StatusBadge`). Warning-coloured text would fail AA, so it isn't used.
2. **Secondary text is never placed on Tint or Fill backgrounds**, only on Surface or Canvas.
3. Status is always icon + text, never colour alone (DRD §11).

## Typography (DRD §3)

- Geist Sans for UI and body, and Geist Mono for SQL, model IDs, versions, latency and request IDs. Both are self-hosted via the `geist` package (`next/font/local`), so builds need no network access.
- Scale: 12px metadata · 13–14px labels · 14px body (line-height 1.5) · 18px section titles · 26px page titles.
- `tabular-nums` applies to all numbers in metrics, tables and times.
- Uppercase is used only for small eyebrow metadata (for example, the date on Overview).

## Layout & spacing (DRD §4, §10)

- Sidebar 240px fixed at ≥1024px. Below that, a left drawer (`Sheet`). The top bar is 56px. Content max width is 1440px.
- Page padding is 16 / 24 / 32px (mobile / tablet / desktop). Spacing uses a 4px base.
- Radius: controls 8px (`rounded-lg`), cards ~11px (`rounded-xl`). Pills are reserved for compact status chips.
- 1px low-contrast borders. Shadows appear only on overlays (sheet, tooltip, popover).
- Grid tracks holding long content use `minmax(0, …)` so they never cause horizontal page scroll.

## Icons (DRD §5)

Lucide (`lucide-react`) only, with no emoji. Navigation icons are 18px with stroke 1.75, inline icons 16px. Mapping:
Overview `LayoutDashboard`, Library `Files`, Ask `MessagesSquare`, SQL `Database`, Evaluation `FlaskConical`,
Models `Cpu`, Activity `Activity`, Help `BookOpen`, success `CircleCheck`, warning `TriangleExclamationPoint`
(lucide v1 name for alert-triangle), error `CircleX`.

## Brand

`components/brand/logo.tsx` is a stroke-only folded page with three linked evidence nodes, plus a typographic wordmark.
`app/icon.svg` is the same mark in white on teal. No gradients.

## Interaction & motion (DRD §9)

- Default transition is 150ms, and drawers/dialogs use the shadcn defaults (~200ms). `prefers-reduced-motion` removes them (globals.css).
- Visible 2px teal focus ring on every focusable element. Skip link to `#main`. Radix primitives provide focus trapping and Escape handling.
- Unbuilt pages appear in navigation **disabled with an explanation** (milestone tag + tooltip + screen-reader text) rather than as dead links.

## Required states (DRD §13)

Every data region implements loading (skeleton matching the final layout), empty, error (plain-language reason, recovery
action, request ID when available), success, disabled-with-reason, partial, and model-unavailable states.
The Overview readiness panel is the reference implementation.
