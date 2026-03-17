# News Feed Magazine UI Design

## Context

The current frontend has two visible issues in the news experience:

1. The left sidebar uses a vertically centered layout that makes the navigation feel detached from the page structure.
2. The news feed uses a fixed-height virtual list (`184px` rows), while titles and summaries are variable-length. This causes severe text overlap and makes the feed unreadable for long Chinese headlines.

The user wants the news page to feel more like a magazine front page:

- top stories should be more prominent
- secondary stories should flow downward in reading order
- the UI should look more polished and editorial, not like a tool dashboard

The user selected:

- visual direction: magazine-style layout
- page priority: highlight top stories first
- lead-story ranking: hybrid scoring, with importance first and recency as the tie-breaker / freshness signal

## Goals

- Replace the current dense tool-like news layout with an editorial layout.
- Make the lead story visually dominant on first screen.
- Prevent all title/summary overlap issues by removing fixed-height assumptions from the feed.
- Rework the left navigation into a top-aligned desk-style sidebar.
- Keep the existing API contract intact for this iteration.

## Non-Goals

- No new backend API for editorial grouping in this iteration.
- No manual curation / pinning workflow for lead stories.
- No mobile-first redesign beyond baseline responsive safety.
- No changes to the news detail API schema.

## Proposed Approach

### Option Summary

Three approaches were considered:

1. Frontend-only editorial regrouping with a computed ranking layer.
2. Backend-provided lead/supporting/stream sections.
3. Minimal list fix without structural redesign.

The chosen approach is option 1 because it solves the layout and readability problems without expanding this task into an API redesign.

## Information Architecture

The news page will be restructured into three editorial layers.

### 1. Edition Header

The top of the page becomes a compact edition header:

- page title
- short editorial subtitle
- lightweight filters for market, sentiment, source, and search

The filters remain available, but visually they should read as controls attached to the edition rather than a large form block.

### 2. Lead Story

The first viewport section contains one lead story spanning the full content width:

- large headline
- summary/excerpt
- source, publish time, market tag, and sentiment tag
- optional topic / related-stock signals if available

This replaces the current split-screen pattern where list and detail compete for attention.

### 3. Story Stream

Below the lead story, the page presents:

- a small set of supporting stories
- then a longer flowing list of standard story cards

All story cards use variable height. No row in the feed may assume a fixed content height.

The persistent right-side detail panel will be removed from the main news index. The index page becomes a reading surface first. Detailed inspection remains available via per-item interaction and the existing news detail route.

## Lead Story Ranking

The frontend will compute an `editorialScore` using existing fields only.

### Inputs

- `topic.importance_score` when detail is available
- publish time freshness
- whether the item has a usable summary
- whether the item has a topic
- number of stock mentions
- whether article extraction produced usable body text

### Ranking Intent

The lead story should not simply be the newest item.

It should prefer:

- stories tied to stronger topics
- stories that have enough context to read like a headline package
- stories that are still fresh enough to feel current

### Stability Rules

To avoid disruptive reshuffling:

- regrouping happens on initial load and when filters change
- SSE / incremental updates should not constantly replace the lead while the user is reading
- if detail is still loading, the list fields provide a provisional ranking and the score is refined once detail arrives

## Sidebar Redesign

The sidebar will shift from vertically centered navigation to a top-aligned desk-style column.

### Structure

- brand block at the top
- primary navigation block below it
- connection/system status block at the bottom as secondary metadata

### Visual Intent

- eliminate the floating / centered feeling
- reduce visual dominance versus the news surface
- keep active state clear but calmer
- use grouping and spacing so the sidebar feels anchored to the page

## Layout and Typography

### Page Rhythm

- more vertical spacing between major sections
- stronger distinction between lead, supporting, and standard stories
- reduced panel density

### Typography

- larger lead headline scale
- cleaner line-height for long Chinese headlines
- summary text constrained to readable widths
- metadata visually subordinate to headline and summary

### Card Rules

- cards expand naturally with content
- summaries are clamped intentionally rather than overflowing
- source/time/tags share a consistent metadata row

## Data and Interaction Behavior

- Existing filters remain active and continue to drive the same REST query.
- The visible feed is derived from filtered results after editorial sorting.
- Selecting a story should still let the user drill into full detail, but the index is no longer dependent on a persistent split-panel detail view.
- Missing detail data must degrade gracefully to title + summary + metadata only.

## Testing Strategy

Follow project TDD requirements for the implementation phase.

Minimum planned coverage:

- unit tests for editorial scoring / grouping logic
- tests for lead-story selection stability with mixed detail completeness
- build verification for the updated frontend layout

Minimum verification commands after implementation:

- `npm --prefix frontend run build`

If the implementation touches shared frontend logic enough to justify broader checks, relevant frontend tests should be added and run as well.

## Risks

### Ranking Quality

Because editorial ranking is inferred from current fields, the lead story may occasionally reflect incomplete detail data. The fallback behavior must remain reasonable even before detail hydration finishes.

### Density Tradeoff

Magazine layout improves readability and hierarchy but reduces same-screen item count. This is acceptable for the selected direction, but spacing still needs to stay disciplined.

### Existing Interaction Expectations

Removing the persistent detail pane changes the scanning pattern of the page. The replacement interaction needs to remain fast enough that users do not lose access to topic/stock context.

## Implementation Outline

Planned implementation areas:

1. Extract frontend editorial ranking and grouping helpers.
2. Add tests for ranking and grouping.
3. Replace the fixed-height virtual feed on the news page with magazine-style sections.
4. Redesign the sidebar structure and spacing.
5. Polish typography, card spacing, clamping, and metadata presentation.
6. Verify frontend build and update code-change-log.
