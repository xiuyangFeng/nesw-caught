# Watchlist Suite Terminal Midstate Design

## Context

After refining the shared shell, Dashboard, and News Feed, the remaining highest-traffic pages that still sit in the older visual layer are:

1. Watchlist
2. Watchlist Detail
3. Topic Detail

These routes already have the correct product responsibilities and data behavior. The main issue is visual drift:

- `Watchlist` still presents the add/search flow and related-news column with softer, older treatment
- `Watchlist Detail` reads as a standard detail page rather than a single-asset monitoring station
- `Topic Detail` exposes dense filters and grouped source cards, but the toolbar and content modules are still one style generation behind the new shell/dashboard/feed midpoint

## Goals

- Bring the remaining high-frequency workflow pages into the same "cold-blue base with orange focus" terminal midpoint.
- Keep all routing, data loading, filtering, and detail navigation behavior intact.
- Make Watchlist feel like an operational workspace rather than a standard management form.
- Make Watchlist Detail feel like a focused single-asset monitor.
- Make Topic Detail filters and grouped-source cards feel like analytical tooling instead of generic panels.

## Non-Goals

- No store, API, or route changes.
- No ranking or grouping logic changes.
- No new metrics or fake telemetry.
- No redesign of page responsibilities.

## Chosen Direction

### Watchlist

Treat Watchlist as a dual-column workstation:

- left side becomes a compact control station for search, candidate selection, and table scanning
- table treatment becomes harder, denser, and more aligned with the shell
- right-side related news adopts the same stream-card language as News Feed

### Watchlist Detail

Treat the detail page as a single-symbol monitor:

- top summary gains a stronger "signal module" feel
- metric cards tighten into more technical, smaller terminal modules
- related-news cards align with the terminal-card language already used elsewhere

### Topic Detail

Treat Topic Detail as an analytical investigation board:

- toolbar becomes a tighter control strip
- grouped source cards gain stronger borders, labels, and action alignment
- timeline mode should read like a structured signal chronology, not a stack of generic panels

## Component Boundaries

### WatchlistView

May change:

- section headings and micro-labels
- candidate-list styling
- action button styling
- related-news preview cards

Must not change:

- candidate filtering
- add/delete behavior
- related news loading behavior

### WatchlistTable

May change:

- table shell styling
- row emphasis
- header density and stable test hooks

Must not change:

- row selection behavior
- delete button event behavior

### WatchlistDetailView

May change:

- summary and metric card styling
- related-news card hierarchy

Must not change:

- quote detail loading
- related news loading

### TopicDetailView

May change:

- toolbar presentation
- grouped source card presentation
- timeline card presentation

Must not change:

- filtering semantics
- grouped/timeline mode logic
- news-detail navigation

## Acceptance Criteria

- Watchlist, Watchlist Detail, and Topic Detail visually align with the refined shell/dashboard/feed midpoint.
- Existing user interactions remain unchanged.
- Relevant view/component tests pass after updates.
- Frontend build passes.
