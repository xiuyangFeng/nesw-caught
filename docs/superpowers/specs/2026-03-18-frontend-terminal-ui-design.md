# Frontend Terminal UI Design

## Context

The current frontend already has a workable information architecture, but its visual language conflicts with the product's domain.

Visible issues in the existing UI:

1. The global palette is warm, bright, and paper-like. It feels editorial and lifestyle-oriented rather than financial and technological.
2. The sidebar, cards, and filters use soft surfaces and low-contrast treatment, so the application reads more like a polished content site than a monitoring terminal.
3. Important system states, market signals, and news priorities do not have a strong visual hierarchy. The interface does not feel decisive enough for a news and watchlist workflow.

The user wants the frontend to feel:

- darker, cooler, and more professional
- more technological and financial
- closer to a terminal / research workstation than a bright magazine layout

The user explicitly selected:

- overall direction: terminal-style financial UI
- page priority: global shell and shared visual system first
- visual blend: mostly hard-edged terminal character, with a limited amount of modern polish
- highlight strategy: orange as the primary signal, blue as a secondary system/status signal
- density target: medium-high density, not an old-school wall of data

## Goals

- Replace the warm bright magazine palette with a dark terminal-oriented visual system.
- Rebuild the shared shell, surfaces, and controls so every primary route inherits the new language.
- Increase contrast and information density without making the interface claustrophobic.
- Make News Feed and Dashboard feel like parts of the same market workstation.
- Preserve current route structure, API contracts, and component responsibilities as much as possible.

## Non-Goals

- No backend API or data-model changes.
- No route restructuring or new navigation destinations.
- No full redesign of every page's information architecture in this iteration.
- No attempt to mimic legacy Bloomberg screens one-to-one.
- No animated trading dashboard gimmicks, charting system, or synthetic market widgets beyond the current product scope.

## Proposed Approach

### Option Summary

Three visual strategies were considered:

1. Pure classical terminal: extremely hard-edged black/orange interface with minimal polish.
2. Terminal-first with selective modern refinement.
3. Dark institutional research desk with lower signal intensity.

The chosen approach is option 2.

This keeps the cold terminal backbone the user wants while avoiding a dated or overly harsh interface. The UI should still feel current, but the polish must support the terminal character rather than soften it into a generic SaaS dashboard.

## Acceptance Boundaries

The following boundaries define what "done" means for this iteration:

- density target means reducing the dominant desktop padding, gap, and card-radius values by roughly 10% to 25% compared with the current implementation, while keeping headlines and summaries readable without overlap or clipping
- limited modern polish means subtle gradients, restrained hover/focus transitions, and occasional inner highlights are allowed, but large glassmorphism blur, oversized glows, and decorative animation loops are out of scope
- stronger shell separation means the sidebar, main workspace, and status module must remain visually distinct at desktop widths through darker surfaces, border contrast, and active-state signaling rather than through large empty gaps
- more decisive hierarchy means each primary page must expose one obvious first-read focal area above the fold through contrast, typography, and signal color, without requiring structural route changes

These are implementation constraints, not invitations to redesign product behavior.

## Visual System

### Base Palette

The global palette will shift from warm paper tones to cold dark navy/charcoal layers.

Recommended token direction:

- app background: near-black blue
- elevated background: slightly lighter blue-black
- panel background: dark steel/navy
- borders: faint cool gray-blue
- primary text: high-contrast off-white
- secondary text: muted blue-gray

The result should feel deep and technical, not decorative.

### Signal Color Strategy

Color roles will become explicit:

- orange: editorial focus, active navigation, current selection, primary action, lead story emphasis
- blue: system state, stream/connectivity status, filters, supporting technical affordances
- green/red: market-positive and risk-negative states only

Blue must remain secondary. If blue becomes dominant, the UI will drift toward a generic product console instead of a financial terminal.

### Typography

The existing `IBM Plex Sans` base can remain for readability, but terminal cues should be strengthened through typographic hierarchy:

- tighter and heavier page titles
- stronger uppercase micro-labels
- optional monospace use for timestamps, index numbers, and system metadata

Typography should communicate decisiveness and scanability, not warmth.

## Shell and Navigation

### App Shell

The shell remains a left-sidebar + main-workspace layout, but its treatment changes substantially.

The sidebar should become a proper terminal control column:

- stronger separation from the main workspace
- more structured brand area
- clearer active-state indication
- status panel that feels like a live system module instead of a soft informational card

### Sidebar Structure

The current structure is conceptually sound and will be preserved:

1. brand/system header
2. primary navigation
3. live connection/status module

What changes is the visual language:

- tighter spacing
- firmer edges
- less decorative copy
- stronger active signal through orange highlights
- blue reserved for connectivity/system details

### Refactor Boundary

This redesign may change:

- templates, class names, CSS variables, and scoped styles
- component markup where needed to support hierarchy and styling
- non-behavioral copy for shared headings or section labels on Dashboard and News Feed

This redesign must not change:

- route paths or route names
- REST/SSE contracts and store interfaces
- navigation destinations
- page-level business logic, ranking logic, or data-fetching behavior except for incidental wiring needed to preserve current rendering

## Shared Surfaces and Controls

### Surfaces

Shared cards and sections will move away from the current milky translucent paper feel.

Panel rules:

- darker solid or near-solid panels
- thinner, clearer borders
- restrained shadowing
- slight internal highlight or subtle gradient where needed
- less blur-heavy glass treatment

Surfaces should feel like modules in an operations console.

### Control Bar and Inputs

Filters and search controls should look like market-workstation controls rather than form widgets:

- dark input surfaces
- blue focus states
- tighter spacing
- stronger visual grouping

This is especially important on the News Feed page, where the filter bar should read as an instrument row attached to the feed rather than a generic search form.

### Status and Tagging

Pills, badges, and banners should be standardized by meaning:

- system/live/stream states use blue
- editorial/active/focus states use orange
- market polarity uses green/red
- neutral tags stay cool gray

This gives users a consistent decoding model across pages.

## Page-Level Direction

### News Feed

The existing editorial grouping structure introduced recently is directionally correct and should remain:

- lead story
- supporting stories
- story stream

The change here is not the information architecture; it is the visual treatment.

The page should feel like the main news terminal:

- stronger top-level title treatment
- more decisive lead-story block
- tighter supporting-story modules
- stream cards that scan like signals rather than magazine tiles

Allowed copy updates on this page are limited to shared section headings and small UI labels such as section titles, status labels, and filter-group labels. Story content, route names, and business terminology from data sources are out of scope.

### Dashboard

Dashboard should become the control-room summary page.

Desired character:

- compressed but readable top metrics
- modular monitoring boards below
- latest-news and market-movement areas treated as live operational panels

It should feel like a market overview workspace, not a general homepage.

### Other Routes

Watchlist, detail pages, and settings should inherit the new token system and shared components, but they are secondary in this iteration.

The priority is to make sure they no longer visually clash with the new shell and shared surfaces.

## Interaction and Motion

Motion should stay subtle and purposeful:

- hover and focus transitions only where they clarify affordance
- no decorative floating or glowing animation loops
- optional stagger or fade on page-level section entrance only if it remains restrained

The interface should feel live, not playful.

## Responsiveness

Desktop remains the primary target, but the redesign must preserve safe rendering at narrower widths.

Requirements:

- the shell must remain a two-column sidebar/workspace layout above `1100px`
- the shell must collapse to a single-column stacked layout at `1100px` and below
- filter bars wrap without creating bright visual clutter
- multi-column story or dashboard sections may collapse progressively between roughly `1320px`, `1100px`, and `768px`, but must never leave clipped text or horizontal overflow in the main content area
- card density should reduce by column collapse and smaller spacing, not by reintroducing bright empty surfaces

This is not a mobile-first redesign, but the dark terminal language must degrade cleanly.

## Accessibility and Legibility Requirements

The redesign must preserve or improve the current basic accessibility baseline.

Requirements:

- body text and primary labels must maintain readable dark-theme contrast; muted text can be softer, but primary reading text must remain clearly legible on panel backgrounds
- interactive focus states must remain visible on keyboard navigation and cannot rely on color alone
- positive, negative, system, and focus states should combine color with text, placement, or iconography/patterned grouping where practical so status meaning is not carried only by hue
- hover-only affordances are insufficient for critical controls

## Testing Strategy

Implementation must follow project TDD requirements.

Minimum planned verification:

- update or add frontend tests that cover any changed component contracts
- run the full frontend test suite
- run frontend build verification

If visual refactors change DOM structure that existing tests depend on, tests should be updated deliberately rather than removed.

## Risks

### Over-Correcting into Generic Dark SaaS

If corners stay too soft, blue is overused, or panels become too glassy, the result will look like a generic admin tool rather than a financial terminal.

### Over-Correcting into Harsh Legacy Terminal

If density becomes too aggressive or orange is used too widely, the interface will feel outdated and visually tiring.

### Inconsistent Semantic Color Use

If orange, blue, and positive/negative states are mixed inconsistently across components, the interface will lose the signal clarity this redesign depends on.

### Accessibility Regressions

Dark terminal interfaces fail quickly when muted text becomes too dim, focus states disappear, or semantic meaning depends only on hue. This redesign must avoid those regressions while tightening the visual language.

## Implementation Outline

Planned implementation areas:

1. Replace global visual tokens in `frontend/src/assets/main.css`.
2. Redesign `AppShell.vue` into a terminal-style navigation and system column.
3. Update shared primitives such as section cards, banners, pills, and filter controls.
4. Re-skin News Feed around the existing editorial hierarchy.
5. Re-skin Dashboard to match the new workstation language.
6. Run frontend verification and update `docs/code-change-log.md`.
