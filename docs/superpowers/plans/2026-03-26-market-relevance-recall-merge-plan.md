# Market Relevance Recall Merge Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the concept-mover and shipping-route keep experiments into `main` and regenerate the research artifacts from the combined evaluator.

**Architecture:** Keep the current evaluator structure and add two narrow heuristics behind focused regression tests. Regenerate one new combined experiment artifact and point the report and ledger at that artifact so `main` reflects the merged result.

**Tech Stack:** Python, pytest, project evaluation scripts, Markdown/TSV research artifacts

---

## Chunk 1: TDD Merge

### Task 1: Add the failing regression tests

**Files:**
- Modify: `backend/tests/test_news_relevance_evaluator.py`

- [ ] **Step 1: Write the failing tests**

Add four tests:
- concept mover positive
- generic product concept negative
- shipping route disruption positive
- generic Gaza humanitarian update negative

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'concept_mover or shipping_route_disruption or generic_product_concept or generic_gaza_humanitarian_updates' -q`
Expected: FAIL because `main` does not yet include the two heuristics.

### Task 2: Implement the minimal evaluator changes

**Files:**
- Modify: `backend/app/services/news_relevance_evaluator.py`
- Test: `backend/tests/test_news_relevance_evaluator.py`

- [ ] **Step 3: Add the concept-mover and shipping-route heuristics**

Implement only:
- concept-sector terms + explicit equity move terms
- shipping actor terms + route disruption phrases

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -k 'concept_mover or shipping_route_disruption or generic_product_concept or generic_gaza_humanitarian_updates' -q`
Expected: PASS

## Chunk 2: Artifact Refresh

### Task 3: Regenerate the combined experiment outputs

**Files:**
- Create: `backend/data/research/market_relevance_experiment_recall_merge/evaluation.json`
- Create: `backend/data/research/market_relevance_experiment_recall_merge/evaluation.md`
- Modify: `docs/research/market-relevance-experiments.tsv`
- Modify: `backend/data/research/market_relevance_report.md`
- Modify: `backend/data/research/market_relevance_report.html`
- Modify: `docs/code-change-log.md`

- [ ] **Step 5: Run the full evaluator test file**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -q`
Expected: PASS

- [ ] **Step 6: Run compile checks**

Run: `conda run -n news-caught python -m py_compile backend/app/services/news_relevance_evaluator.py backend/scripts/evaluate_market_relevance.py backend/scripts/render_market_relevance_report.py`
Expected: PASS

- [ ] **Step 7: Generate the combined evaluation artifact**

Run: `DATABASE_URL=sqlite:////Users/xiuyang/Desktop/news-caught/backend/data/app.db conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir backend/data/research/market_relevance_experiment_recall_merge`

- [ ] **Step 8: Record the keep experiment**

Run: `conda run -n news-caught python backend/scripts/run_news_relevance_experiment.py --experiment-id exp-20260326-recall-merge --baseline-id exp-20260325-index-signals --hypothesis "Combine concept-mover and shipping-route recall improvements" --changed-file backend/app/services/news_relevance_evaluator.py --metrics-before backend/data/research/market_relevance_experiment_index_signals/evaluation.json --metrics-after backend/data/research/market_relevance_experiment_recall_merge/evaluation.json --ledger docs/research/market-relevance-experiments.tsv`

- [ ] **Step 9: Refresh the report**

Run: `conda run -n news-caught python backend/scripts/render_market_relevance_report.py --benchmark backend/data/research/market_relevance_benchmark.jsonl --evaluation backend/data/research/market_relevance_experiment_recall_merge/evaluation.json --ledger docs/research/market-relevance-experiments.tsv --markdown-output backend/data/research/market_relevance_report.md --html-output backend/data/research/market_relevance_report.html`

- [ ] **Step 10: Update the code change log**

Add a top entry summarizing the merged heuristics, generated artifact, and verified commands.
