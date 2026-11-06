<!-- Generated from KnowFlow_DRD_Design_Requirements.docx (authoritative source). Do not edit by hand. -->
KNOWFLOW
# Design Requirements Document
Visual identity, design system, interaction patterns, page layouts, accessibility and product polish

| DOCUMENT CONTROL | VALUE |
|---|---|
| Document ID | DRD-001 |
| Version | 1.0 |
| Status | Baseline specification – update decisions in the repository |
| Product | KnowFlow – Local-first Enterprise Knowledge Intelligence |
| Owner | Solo developer / project maintainer |
| Date | 06 November 2026 |


## How to use this document
Give this document to the coding agent as an authoritative project specification. The agent must read all three documents (TRD, PRD and DRD) before changing code. If two documents appear to conflict, use the priority rules in the PRD and record the resolution in docs/decisions/ rather than silently inventing a design.
Important: this specification defines the intended product and acceptance criteria. It does not claim that implementation, benchmark results, security certification or deployment already exist.

## 1. Design direction
KnowFlow should look like a carefully crafted professional knowledge-work product: calm, editorial, precise and trustworthy. It should feel closer to a modern research/analytics workspace than a chatbot template. The interface must communicate evidence, clarity and control.

| Design principle | What it means in practice |
|---|---|
| Human-made, not AI cliché | No purple/blue neon gradients, glowing orbs, robot mascots, floating glass cards or random sparkle icons. |
| Editorial clarity | Strong typography hierarchy, generous whitespace, clear labels, restrained dividers and readable content widths. |
| Evidence first | Citations, source metadata and SQL preview are first-class UI elements, not tiny footnotes. |
| Quiet confidence | Mostly neutral surfaces with one restrained accent color; status colors only for meaningful states. |
| Data density with rhythm | Tables and evaluation charts can be information-rich but must retain spacing, alignment and clear labels. |
| Functional motion | Motion explains state changes; never animate for decoration or slow down work. |


## 2. Brand identity and visual language
Brand personality: intelligent, grounded, composed, dependable, technical without looking intimidating. The wordmark should be typographic. A simple abstract mark may combine a page corner, linked evidence nodes or a subtle folded document motif; avoid a literal robot or brain.

| Token | Value | Usage |
|---|---|---|
| Canvas | #F6F5F1 | Warm off-white app background; use sparingly on large surfaces. |
| Surface | #FFFFFF | Main cards, menus, panels and content surfaces. |
| Ink | #202B33 | Primary text and headings. |
| Secondary text | #65717A | Descriptions, metadata and helper labels. |
| Primary accent – deep teal | #245B57 | Primary actions, active nav, links and selected states. |
| Accent tint | #E8F0ED | Subtle selected/active background; not a gradient. |
| Border | #E3E6E3 | Dividers, table borders and input outlines. |
| Success | #287A55 | Completed/healthy states only. |
| Warning | #A66A1F | Warnings and attention states. |
| Danger | #B54742 | Errors, destructive actions and blocked SQL. |
| Info | #496D8C | Neutral informational state. |

Use a light theme as the primary design. A dark theme may be added only after light mode is complete and tokenized. Do not use gradients as a core brand element. Avoid pure black; use Ink. Use accent color with restraint (roughly 5–10% of visible interface).

## 3. Typography

| Role | Font recommendation | Guidance |
|---|---|---|
| UI and body | Inter or Geist Sans | Use one family consistently; if using Geist, bundle via next/font. |
| Headings | Same family, semibold | Avoid oversized marketing headings inside app screens. |
| Technical values / SQL / IDs | Geist Mono or IBM Plex Mono | Use for SQL, model IDs, latency, request IDs and code snippets. |
| Numbers | Tabular numerals | Align metric cards, tables and evaluation values. |

Recommended scale: 12px metadata, 13–14px compact labels, 14–16px body, 18–20px section titles, 24–28px page title. Use 1.45–1.65 line height for body. Avoid all-caps for long labels; use small uppercase only for eyebrow metadata.

## 4. Layout and spacing system
- Desktop app shell: fixed left navigation rail/sidebar around 232–248px; top header 56–64px; content max width around 1440px.
- Use a 4px base spacing unit with common increments 4, 8, 12, 16, 20, 24, 32, 40 and 48px.
- Main page padding: 28–32px desktop, 20–24px tablet, 16px mobile.
- Card radius: 10–12px. Inputs/buttons: 8px. Avoid excessive pill shapes; reserve pills for compact status labels.
- Borders should be 1px and low contrast. Shadows should be subtle and used only for overlays/popovers, not every card.
- Use a 12-column grid for dashboard pages where helpful; preserve consistent gutters.
- Use content-first layouts: do not force every screen into a dashboard of equal-sized cards.

## 5. Iconography and illustration
Use Lucide icons through lucide-react. Keep icons 16–20px for navigation and controls, 14–16px inline, and 20–24px for empty-state illustrations. Use consistent 1.75–2px stroke. Never mix emoji icons with Lucide in the product UI.

| Purpose | Suggested Lucide icon |
|---|---|
| Overview | layout-dashboard |
| Knowledge Library | files / folder-open |
| Ask KnowFlow | messages-square |
| SQL Analyst | database / table-2 |
| Evaluation Lab | chart-no-axes-combined / flask-conical |
| Models | cpu |
| Activity | activity / list-checks |
| Upload | upload |
| Citation/source | file-text / quote |
| Search | search |
| Settings | settings-2 |
| Success | check-circle-2 |
| Warning | alert-triangle |
| Error | circle-x |
| External link | external-link |

Use CSS/SVG diagrams for architecture and retrieval flows. Use real screenshots of the product in the README. Avoid stock photos; this is a technical product and interface evidence is more credible.

## 6. Application shell

### 6.1 Sidebar
- Top: small KnowFlow wordmark and restrained mark.
- Workspace switcher or local workspace name below the wordmark.
- Primary navigation: Overview, Knowledge Library, Ask KnowFlow, SQL Analyst, Evaluation Lab.
- Secondary navigation anchored near bottom: Models & Settings, Activity, Help / documentation.
- Active nav uses a light teal tint, dark teal icon and text; no glowing highlight.
- Collapsed sidebar may be supported on smaller desktop; mobile uses a drawer.

### 6.2 Top bar
- Left: current page title / breadcrumb.
- Right: system status indicator (Local models ready / Needs setup), help link and small profile/workspace control if needed.
- No decorative search bar unless it performs a real global search.
- Keep top bar visually quiet and consistent across routes.

## 7. Screen-by-screen design requirements

### 7.1 Overview

| Region | Content and behaviour |
|---|---|
| Page intro | Title 'Good morning' is optional; prefer 'Workspace overview' with a short useful sentence and current date. |
| System readiness | Compact status row for PostgreSQL, Ollama, generation model and embedding model. Each item has a clear state and remediation link. |
| Key metrics | Documents indexed, total chunks, recent questions, latest evaluation score. Only show metrics backed by real data; no fake demo counts. |
| Recent activity | Latest uploads, ingestion completions/failures and evaluation runs. |
| Quick actions | Upload documents, Ask a question, Run evaluation. Buttons lead to working flows. |

Visual: one wide welcome/health area, a small number of metric cards, then a two-column activity/quick-actions layout. Avoid a wall of cards.

### 7.2 Knowledge Library
- Header includes title, indexed-document count and primary Upload documents button.
- Upload dropzone is compact, bordered and practical; show supported types and size limit.
- Document list/table columns: name/type, status, pages, chunks, last indexed, actions.
- Use document-type icons, not colorful file thumbnails.
- Status uses small text + icon; failed rows expose a clear retry action and safe error details.
- Document detail drawer shows extraction preview, page count, chunk count, checksum/version and chunk sample.
- Empty state explains what to upload and includes one real CTA.

### 7.3 Ask KnowFlow
- Main area resembles a focused research workspace, not a consumer chat clone.
- Top control row: source scope (all documents or selected), retrieval profile, and optional show-retrieval-details toggle.
- Conversation column has comfortable reading width (around 760–860px).
- Composer is a clear bordered textarea with send button, keyboard shortcut hint and selected source scope.
- Answer typography should support headings, paragraphs, lists and code without overly decorative formatting.
- Citations appear as restrained numbered inline chips such as [1], [2]. Clicking opens a right-side source drawer.
- Source drawer shows file title, page/section, exact excerpt, and open-document action.
- A small 'Evidence quality' line may show retrieved sources count and abstention status; never display an uncalibrated confidence percentage.
- Loading state shows meaningful stages (Searching sources… / Preparing answer…) only when those stages are real.

### 7.4 SQL Analyst
- Use a two-panel layout: left schema browser and question history; right question/clarification/SQL/result workspace.
- Schema browser lists allowed schemas, tables, columns and types with clear expand/collapse.
- Clarification is a distinct decision panel with selectable options; avoid a chat bubble that hides the choice.
- Generated SQL appears in a syntax-highlighted, read-only code panel with copy action.
- Run/execute control is visually separate and explicit; show read-only badge and database name before execution.
- Results table supports horizontal scroll, sticky header and empty/error states.
- Show query duration and returned row count; no fake charts unless the query result supports one.

### 7.5 Evaluation Lab
- Header explains that evaluation compares retrieval/generation configurations on a fixed dataset.
- Configuration panel: dataset version, chunking strategy, dense/lexical/hybrid, top-k, reranker, model and prompt version.
- Run button creates an asynchronous evaluation job; show progress and allow safe navigation away.
- Comparison view should use a clear table as the primary artifact; charts are secondary.
- Metric cards show label, value, sample count and tooltip definition. Distinguish retrieval metrics from answer-judge metrics.
- Per-case inspection is a split view: question/reference on left; retrieved passages, answer and failure category on right.
- Use neutral chart palette and direct labels. Do not use red/green as the only way to distinguish configurations.

### 7.6 Models & Settings
- Show local runtime status and installed model names as plain text rows.
- Separate generation model, embedding model and reranker settings.
- Show model size and resource note only when verified from runtime metadata/model listing.
- Embedding model change requires a strong warning that existing vectors need rebuilding.
- Provide copyable setup commands and a Validate configuration action.
- No cloud provider cards, pricing upsells or API-key fields in v1.

## 8. Component library requirements

| Component | Variants / states |
|---|---|
| Button | Primary teal, secondary outline, tertiary text, destructive; default, hover, focus, disabled, loading. |
| Status badge | Ready, Processing, Queued, Failed, Needs setup; neutral first, semantic colors only for status. |
| Data table | Sortable headers where useful, pagination, empty/loading/error states, row action menu. |
| Citation chip | Default, hover, selected; keyboard accessible and opens source drawer. |
| Source drawer | Document metadata, page/section, excerpt, open action, close control. |
| Metric card | Metric name, value, sample count, delta only when comparison is valid, tooltip. |
| Code block | SQL/Python, copy, line wrap/scroll, read-only label. |
| Upload dropzone | Idle, drag-over, uploading, rejected, complete. |
| Clarification panel | Question, 2–4 choices, optional 'other/define metric', explicit confirm. |
| Toast | Success/error/info; short, actionable, non-blocking. |
| Skeleton | Use for actual loading content; avoid shimmer overload. |
| Modal/dialog | Confirm delete, connection test result, destructive operation. |


## 9. Interaction, motion and feedback
- Use transitions around 120–180ms for hover/focus and 180–240ms for drawers/dialogs.
- No parallax, animated gradients, glowing cursor, floating particles or looping decorative motion.
- Respect prefers-reduced-motion; remove non-essential transitions when enabled.
- Every async action has immediate feedback, a progress/status state and a useful failure path.
- Use optimistic updates only for reversible UI state; never optimistically mark ingestion or evaluation as completed.
- Destructive actions require confirmation and explain what is deleted.
- Keyboard support: tab order, Enter/Space activation, Escape close, focus trap in modal and visible focus ring.

## 10. Responsive behaviour

| Viewport | Behaviour |
|---|---|
| Large desktop 1440px+ | Full sidebar, wide content, SQL split panels, source drawer. |
| Laptop 1024–1439px | Sidebar can collapse; tables remain usable; content gutters reduce. |
| Tablet 768–1023px | Sidebar becomes compact/drawer; multi-column layouts stack; SQL schema panel becomes collapsible. |
| Mobile below 768px | Single-column screens; navigation drawer; source drawer becomes full-screen sheet; tables scroll horizontally; composer stays usable above keyboard. |


## 11. Accessibility and content design
- Meet WCAG 2.2 AA contrast targets for text and interactive controls wherever practical.
- All inputs have visible labels; placeholders are examples, not labels.
- All icon-only controls have accessible names and tooltips.
- Status is never conveyed by color alone; include text/icon.
- Tables use semantic headers; charts have textual summaries and accessible labels.
- Error messages explain what happened and how to recover; do not expose stack traces.
- Use plain language: 'No supporting source found' instead of 'RAG confidence below threshold'.
- Avoid anthropomorphic claims such as 'I read everything' or 'I understand your company'.

## 12. Design and implementation tools

| Tool | Use |
|---|---|
| Figma (free tier) or Penpot | Optional wireframes and page flows; do not block implementation on a large design system. |
| Next.js + Tailwind CSS | App layout, responsive styling and design tokens. |
| shadcn/ui | Accessible primitives such as Dialog, Sheet, Dropdown, Tabs, Table, Tooltip, Toast and Command; customize styling. |
| Lucide React | Consistent icons. |
| Recharts or Tremor-style charts | Evaluation charts only when a chart makes comparison clearer; prefer Recharts with accessible labels. |
| Playwright | Visual and end-to-end checks across desktop/mobile viewports. |
| Storybook (optional) | Only add if component complexity warrants it; not required for solo v1. |

Do not add multiple UI component libraries. Prefer shadcn/ui + Tailwind + Lucide. Avoid installing a large dashboard template and merely changing its logo/colors.

## 13. Required states for every screen

| State | Design requirement |
|---|---|
| Loading | Skeleton or stage indicator; avoid blank content. |
| Empty | Explain what belongs here and provide a real next action. |
| Success | Confirm outcome with useful details, not a generic 'Done'. |
| Error | Plain-language reason, request ID when helpful, retry or recovery action. |
| Disabled | Explain why action is unavailable; do not silently disable. |
| Partial | Show what succeeded and what failed; do not label partial ingestion as complete. |
| Offline / model unavailable | Show local runtime status and exact setup/check action. |


## 14. Brand assets and repository deliverables
- Create a simple SVG wordmark and app icon using the page/evidence-node motif; no gradients.
- Store tokens in a central CSS variables file and map to Tailwind/shadcn theme.
- Create a small set of reusable layout and data components; do not duplicate styles per page.
- Add README screenshots for Overview, Knowledge Library, Ask KnowFlow with citations, Evaluation Lab and SQL Analyst.
- Create a concise design-system page in docs/design-system.md with tokens, typography, spacing, icon rules and interaction states.
- Include alt text for meaningful illustrations; decorative marks should be hidden from screen readers.

## 15. Visual quality acceptance checklist
- No generic purple/blue gradient backgrounds, glowing orbs, robot mascots or decorative AI sparkles.
- Consistent type scale, spacing, border radius, icon stroke and color tokens across every page.
- All primary actions work; no dead buttons or fake data cards.
- Every major screen has loading, empty, error and success states.
- Citations and SQL preview are easy to discover and inspect.
- Desktop, tablet and mobile layouts have been manually checked with Playwright screenshots.
- Keyboard navigation and visible focus are functional.
- Charts use real evaluation data and include metric definitions/sample sizes.
- The UI feels coherent as one product, not a collection of copied dashboard templates.

## 16. Example design brief for the coding agent
Design KnowFlow as a calm, premium knowledge-work application. Use warm off-white canvas, white surfaces, deep charcoal typography, restrained deep-teal accent, thin neutral borders and generous whitespace. Use Inter/Geist Sans, Lucide icons and shadcn/ui primitives customized with Tailwind. Avoid gradients, neon, glassmorphism, robot imagery and over-cardification. Prioritize source citations, retrieval transparency, evaluation tables and safe SQL preview. Every screen must be responsive, accessible and fully functional with real backend data.
