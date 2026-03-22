# Dashboard Terminal Midstate Design

## Context

The shell refinement established the shared "cold-blue base with orange focus" direction, but `Dashboard` still visually reads closer to the earlier softer dashboard treatment than to the newly agreed terminal midpoint.

The page already has the correct information architecture:

1. compact header and status badge
2. metric strip
3. three-column desktop layout with feed, topics, and movers

This iteration should not redesign those responsibilities. It should intensify the operational feel of the page.

## Goals

- Keep the current three-column layout and data behavior.
- Make the top metric strip feel more like a monitoring module row.
- Make the topic column feel more like a technical signal board.
- Make the movers column feel like a narrow signal rail instead of a stack of soft cards.
- Keep orange constrained to focal accents rather than turning the whole page orange.

## Non-Goals

- No changes to Dashboard data loading or ranking.
- No route changes.
- No new charts or fake telemetry.
- No changes to API/store contracts.
- No restructuring of News Feed or Watchlist routes in this iteration.

## Chosen Direction

Dashboard will become a "control room" page inside the refined shell:

- header remains concise
- metric cards tighten and gain stronger micro-label hierarchy
- topic cards keep summaries but use firmer framing
- movers column shifts toward compact row-based signal presentation

## Component Boundaries

### DashboardView

May change:

- section labels
- class composition
- compact metadata rows
- mover row presentation

Must not change:

- list slicing logic
- status computation logic
- sentiment routing links

### HeroMetrics

May change:

- card treatment
- label/value/note hierarchy
- stable test hooks for tightened shell modules

### TopicBoard

May change:

- internal card hierarchy
- stable hooks for stronger terminal-card framing

Must not change:

- click-to-route behavior

## Acceptance Criteria

- Dashboard still renders the same modules and routes.
- Metric cards feel denser and more technical.
- Topic cards read as signal modules rather than content cards.
- Movers list is visibly more rail-like and compact.
- Existing Dashboard/HeroMetrics/TopicBoard tests pass after updates.
- Frontend build passes.
