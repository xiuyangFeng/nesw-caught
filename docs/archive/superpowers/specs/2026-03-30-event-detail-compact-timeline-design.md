# Event Detail Compact Timeline Design

**Date:** 2026-03-30

**Context**

`EventDetailView` currently renders each timeline news item as a medium-height card with separate metadata, title, summary, and action rows. After the recent timeline redesign, the page now reads clearly, but the per-card vertical footprint is still too large for dense event tracking. The user wants each card height reduced to at least half of the current presentation so a single screen can carry more event evidence.

**Goals**

- Reduce event timeline card height substantially, targeting roughly half the current visual height.
- Keep the timeline readable without removing the core information hierarchy.
- Preserve current navigation behavior to news detail and source URLs.

**Non-Goals**

- No backend or API contract changes.
- No change to the compact event header above the timeline.
- No semantic change to stage labels or ordering.

**Chosen Approach**

Adopt an ultra-compact card layout for each timeline item:

- Keep metadata pills for stage, source, sentiment, and timestamp in a tighter row.
- Keep the news title, but reduce its font size and line height.
- Keep the summary, but clamp it to a single line with ellipsis.
- Keep both actions, but restyle them as smaller compact actions and remove the feeling of a dedicated tall footer row.
- Reduce card padding, internal gaps, rail spacing, and dot offsets so the whole timeline rhythm becomes denser.

This preserves the current information architecture while reclaiming vertical space from padding, line-height, and oversized controls rather than removing key content.

**Alternatives Considered**

1. Keep the current layout and only shrink paddings/buttons. Lower risk, but unlikely to consistently cut card height in half.
2. Hide the summary entirely. Stronger compression, but the user explicitly asked for a single-line summary rather than removing it.
3. Collapse `打开原文` into a secondary hover-only affordance. Smallest layout, but it weakens discoverability and changes interaction semantics more than necessary.

**Rendering Contract**

- Timeline items remain a rail-based vertical list.
- Each card still shows:
  - stage label
  - source name
  - sentiment label
  - localized market timestamp
  - title
  - single-line summary
  - `查看新闻详情`
  - optional `打开原文`
- Summary fallback text remains `摘要待补充`, but it also uses the same single-line compact treatment.

**Testing Strategy**

- Extend the existing `EventDetailView` test to assert the timeline summary uses a dedicated compact class hook.
- Assert the action area uses the compact action class hook so the new density contract is locked by test.
- Run the targeted view test first in red-green order, then run the frontend build for regression coverage.
