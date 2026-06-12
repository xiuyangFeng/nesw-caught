# Sector News Upgrade Design

**Goal**

Build a first-pass sector-oriented news upgrade for Hong Kong and U.S. market monitoring by improving source quality, deduping repeated media rewrites, and surfacing sector-relevant stories earlier than the current generic market relevance flow.

**Problem**

The current backend mostly ingests `rss` and `html` sources, then applies a boolean market relevance heuristic. That leaves two gaps:

- free aggregator and media sources are noisy, especially for sector rotation use cases
- output still answers "is this market relevant?" more often than "which sector narrative is moving?"

For the first iteration, the system should prioritize sector-level signal detection for:

- `AI/compute`
- `semiconductors`
- `Chinese internet`
- `Apple supply chain / consumer electronics`

Macroeconomic and geopolitical stories remain inputs, but only when they clearly move those sectors.

## Scope

### In Scope

- add one API-based news source type for lightweight aggregator integration
- preserve source tier metadata through ingestion
- add lightweight duplicate suppression beyond canonical URL matching
- extend relevance evaluation from boolean-only filtering to sector tagging
- add a small ranking layer that favors primary sources and sector-relevant stories
- keep the existing research benchmark and experiment loop usable

### Out of Scope

- frontend redesign
- broad topic-clustering refactor
- LLM-first sector classification
- multilingual semantic dedupe
- full event timeline reconstruction
- comprehensive macro/geopolitical ontology

## Source Strategy

The first iteration uses a three-layer source model:

1. `primary`
   - exchange, regulator, central bank, and company IR sources
2. `secondary`
   - real-time or near-real-time aggregator APIs
3. `fallback`
   - delayed or lower-confidence sources used for backfill only

The backend should accept `rss`, `html`, and `api` source types. API sources are configured through the same source registry and normalized into the same `SourceItem` shape.

## Data Flow

The first iteration keeps the existing pipeline structure and adds two steps:

`fetch -> normalize -> duplicate suppression -> relevance + sector tagging -> rank`

Important ordering rules:

- duplicate suppression happens before relevance scoring to avoid repeated rewrites polluting sector counts
- sector tagging is attached during relevance evaluation, not as a later display-only transform
- ranking is metadata-driven and deterministic, not LLM-driven

## Duplicate Suppression

The current model already enforces uniqueness on `canonical_url`. That is not enough for aggregator sources and rewritten headlines.

The first iteration introduces a lightweight duplicate signature based on:

- normalized title text
- source host
- publication time bucket

This signature is used only during refresh to suppress near-identical inserts from the same reporting window. It should not replace canonical URL uniqueness.

## Sector Relevance

The first iteration keeps the current market relevance boolean output, but adds structured sector metadata:

- `sector_tags`: zero or more sector identifiers
- `relevance_reason`: a short machine-readable reason
- `source_tier`: carried from source config for ranking

Rules should remain heuristic and transparent. A story is considered a stronger keep candidate when it:

- mentions a tracked sector directly
- includes market-moving triggers such as guidance, orders, export controls, tariffs, regulation, supply chain disruption, or formal filings
- comes from a primary source

Generic product chatter and soft media features remain noise even if they mention a tracked company.

## Ranking

The first ranking pass should prefer:

1. primary over secondary over fallback
2. sector-tagged stories over generic market-relevant stories
3. filing/regulatory/official updates over media rewrites
4. fresh stories over repeated summaries

The implementation should stay simple enough to test with deterministic unit tests.

## Architecture Notes

- `news_ingestion.py` remains the orchestration point for source loading, fetching, normalization, and insert/update logic
- API source fetching is added as a narrow extension, not a new pipeline
- relevance evaluator continues to serve research benchmarking, but now returns richer prediction metadata through a new helper
- ranking is implemented as a small service module so it can be tested without requiring ingestion side effects

## Verification Strategy

The first iteration is complete when all of the following are true:

- ingestion can load and fetch an API-based source
- duplicate suppression blocks same-window rewritten duplicates during refresh
- relevance evaluation returns the expected sector tags for tracked stories
- ranking favors primary sector stories over lower-tier generic stories
- targeted backend tests pass and the broader regression suite for touched areas stays green
