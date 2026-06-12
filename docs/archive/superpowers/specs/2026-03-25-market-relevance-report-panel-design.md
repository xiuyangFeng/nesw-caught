# Market Relevance Report Panel Design

## Goal

Add a lightweight morning-read report panel for the market relevance autoresearch workflow that renders both Markdown and HTML from existing research artifacts.

## Scope

This design only adds read-only reporting on top of the current benchmark, evaluation, and experiment ledger outputs. It does not change annotation, review, benchmark generation, or baseline evaluation behavior.

## Inputs

The report reads these existing artifacts:

- `backend/data/research/market_relevance_benchmark.jsonl`
- `backend/data/research/market_relevance_baseline/evaluation.json`
- `docs/research/market-relevance-experiments.tsv`

## Outputs

The report generator writes:

- `backend/data/research/market_relevance_report.md`
- `backend/data/research/market_relevance_report.html`

## Report Contents

Both formats should show the same core information:

- latest evaluation metrics
- benchmark sample counts and label distribution
- false positive and false negative sample details with titles
- latest ledger entries
- a short “what changed / what to inspect next” summary

The Markdown output is the durable audit artifact. The HTML output is the fast visual morning-read panel.

## Implementation Shape

- Add a new backend reporting service that loads artifacts and builds a small in-memory report model.
- Add Markdown and HTML renderers in the same service.
- Add a thin CLI script that reads the three inputs and writes both outputs.
- Keep HTML dependency-free: inline CSS only, no frontend app, no build step.

## Error Handling

- Missing required input files should fail clearly.
- If a false positive or false negative id is not present in the benchmark file, the renderer should still show the id and mark the title as missing rather than crashing.

## Verification

- service-level tests for report aggregation and rendering
- CLI test for output generation
- `py_compile` on the new service and script
