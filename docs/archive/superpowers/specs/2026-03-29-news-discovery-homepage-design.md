# News Discovery Homepage Design

**Date:** 2026-03-29  
**Author:** Codex

## Context

The current product surface splits user attention across `Dashboard`, `News Feed`, `Watchlist`, and `X Radar`. That structure makes the product feel feature-rich but weakens the primary promise: helping the user quickly discover new market-relevant events.

The approved product direction for this iteration is:

- Primary value: `news discovery`
- User success condition: open the product and immediately see the latest market- and geopolitics-related events
- Collection strategy: `collect broadly first`, then add filtering and AI ranking later
- Homepage presentation: compact, high-density event stream rather than large showcase cards

## Problem

The current homepage behaves like a control-room summary page. It compresses multiple modules into one surface instead of answering the most important question first:

`What just happened that may matter to markets?`

Specific problems:

- `/dashboard` is a multi-column overview rather than an event-first discovery page
- `/news` already contains event/topic/stream structure, but it is treated as a secondary page
- current event cards are visually larger than needed for a high-volume global event workflow
- supporting modules compete with the discovery surface instead of reinforcing it

## Goals

- Make the homepage a dedicated discovery surface for latest events
- Increase event density so one screen shows substantially more events
- Keep the information model simple enough for future ranking and AI filtering
- Reuse existing backend feed-layout capabilities where possible instead of inventing a new data system

## Non-Goals

- No personalized ranking in this iteration
- No AI filtering or relevance model changes in this iteration
- No redesign of watchlist detail, X Radar detail, or settings pages beyond navigation and supporting-entry adjustments
- No new backend ingestion sources required for this iteration

## Product Design

### 1. Homepage becomes the discovery page

- Route `/` should land on the compact event stream experience
- Route `/news` should remain the canonical discovery route and render the same experience as `/`
- Route `/dashboard` should remain accessible, but as a secondary overview page rather than the default landing page
- `Dashboard` should no longer be the default landing page
- The page title, copy, and information hierarchy should center on latest events, not platform status

### 2. Compact high-density event stream

Each event row should prioritize scan speed over visual drama. Default collapsed state should show:

- event timestamp from existing `events.last_seen_at`
- event type
- event title
- source count from existing `events.source_count`
- impact hints from existing `events.market`, `events.primary_symbol`, and `events.related_symbols`

Collapsed rows should avoid long summaries. Details appear only after row expansion or navigation.

This iteration should not require new backend fields for the compact row design. If any UI field cannot be sourced from the existing `NewsFeedEventCard` payload, it is out of scope for this change.

### 3. Supporting modules become secondary evidence

`X Radar`, `Watchlist`, and topic context still matter, but they should not dominate the homepage. Their role is:

- remain off the first-screen homepage layout
- provide evidence and follow-up context after the user expands an event or navigates into detail
- remain reachable from navigation, but not share first-screen priority with the main event stream

### 4. Future filter-ready structure

The event stream should remain broad for now, but the structure must make future filtering straightforward:

- event rows remain the primary ranking unit
- metadata fields remain visible and structured
- future filtering can operate on the same event list rather than replacing the homepage model

## Technical Design

### Frontend

- Reuse `NewsFeedView` as the primary discovery page rather than building a separate new homepage from scratch
- Reduce card height and vertical spacing in the event list
- Shift page framing and copy from “signal desk” showcase toward “latest events” scanning
- Update router defaults so root navigation lands on the event-first page
- De-emphasize old dashboard-first mental model in shell/navigation labels

### Backend

The existing `feed-layout` endpoint already returns:

- `events`
- `topics`
- `stream`

This iteration should keep `events` as the homepage’s primary content source. Backend changes should stay minimal and only support the compact event-first UX if necessary.

Potential backend refinements allowed within scope:

- ensure event ordering is time-relevant and stable for a “latest events” surface

Event ordering contract for this iteration:

- primary order: existing backend event order from `feed-layout.events`
- frontend rendering must preserve backend event order exactly
- backend event order should continue to prioritize recency-informed event ranking already produced by `NewsFeedLayoutService`
- no frontend-side resorting of event rows is allowed in this iteration

Large feed-ranking changes are explicitly deferred.

## UX Rules

- Latest event rows must dominate first screen real estate
- At the common desktop viewport used by current page tests, the homepage should present at least 5 compact event rows within the primary event section without requiring summary paragraphs inside each row
- Summary text should never push row height into card-like marketing blocks
- Status, diagnostics, and supporting panels must remain visually subordinate

## Testing Strategy

### Frontend

- route/default landing tests for `/`
- `NewsFeedView` rendering tests for compact event-first hierarchy
- shell/nav tests if labels or default routes change

### Backend

- only add or update tests if feed-layout contract changes
- preserve existing event payload compatibility where possible

## Risks

- Event rows may become too compressed if density is pushed without hierarchy discipline
- Reusing `NewsFeedView` could leave legacy topic/stream framing visible unless intentionally reduced
- Existing baseline test failures outside this scope may complicate “all-green” verification and should be tracked separately

## Rollout Outcome

After this change, the product should feel like a focused event discovery terminal instead of a multi-module dashboard. The first screen should answer one question clearly:

`What just happened that I should look at now?`
