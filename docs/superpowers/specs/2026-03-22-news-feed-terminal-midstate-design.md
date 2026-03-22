# News Feed Terminal Midstate Design

## Context

`NewsFeedView` already uses a unified stream layout, but its filter bar and horizontal cards still read slightly softer than the newly refined shell and dashboard.

The goal here is not to change the information architecture. It is to make the feed feel more like an operational news console.

## Goals

- Keep the current unified list order and detail hydration behavior.
- Tighten the filter bar into a more control-station style row.
- Make stream cards feel denser and more terminal-like.
- Preserve existing click-through behavior and source/topic metadata.

## Non-Goals

- No data loading changes.
- No ranking or grouping changes.
- No new feed sections.
- No route changes.

## Acceptance Criteria

- Filter bar remains present but reads as a tighter control row.
- News cards preserve current content but use stronger shell framing and metadata hierarchy.
- Existing NewsFeed/NewsCard tests pass after updates.
- Frontend build passes.
