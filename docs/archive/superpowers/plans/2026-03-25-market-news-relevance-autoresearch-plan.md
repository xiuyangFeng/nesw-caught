# Market News Relevance AutoResearch Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a project-internal research loop that creates a 400-sample market relevance benchmark, evaluates current ingestion/classification behavior against it, and allows a constrained agent to run code-changing experiments only when benchmark results improve.

**Architecture:** Add this in four layers: dataset schema and storage, semi-automatic annotation pipeline using the existing OpenAI-compatible LLM provider path, an offline evaluator that scores market relevance behavior, and a constrained experiment runner that can only touch news relevance files and keeps a structured experiment ledger. Keep all work backend-only and avoid front-end or infrastructure changes.

**Tech Stack:** Python, FastAPI project backend, SQLAlchemy models/repos, pytest, existing OpenAI-compatible `llm_providers`, JSON/JSONL artifacts, project docs/code-change-log discipline

---

## File Structure

- Create: `backend/app/schemas/research.py`
  Purpose: Pydantic schemas for sampled news items, annotation payloads, evaluation results, and experiment ledger rows.
- Create: `backend/app/services/news_relevance_dataset.py`
  Purpose: shared helpers for loading/saving benchmark datasets and validating labels.
- Create: `backend/app/services/news_relevance_annotation.py`
  Purpose: prompt construction, DeepSeek/OpenAI-compatible annotation calls, response parsing, and confidence routing.
- Create: `backend/app/services/news_relevance_evaluator.py`
  Purpose: compute precision/recall/noise rejection and emit machine-readable plus human-readable summaries.
- Create: `backend/app/services/news_relevance_experiment_runner.py`
  Purpose: enforce allowed file scope, run one hypothesis at a time, compare to baseline, and append experiment ledger rows.
- Create: `backend/scripts/sample_market_relevance_dataset.py`
  Purpose: build the initial mixed historical/realtime candidate pool.
- Create: `backend/scripts/annotate_market_relevance.py`
  Purpose: run first-pass model annotation against candidate samples.
- Create: `backend/scripts/review_market_relevance_annotations.py`
  Purpose: surface low-confidence/mandatory-review samples and merge human review decisions into the benchmark set.
- Create: `backend/scripts/evaluate_market_relevance.py`
  Purpose: score a given implementation against the benchmark dataset and emit artifacts.
- Create: `backend/scripts/run_news_relevance_experiment.py`
  Purpose: wrapper for one constrained research experiment run.
- Create: `backend/tests/test_research_schemas.py`
  Purpose: schema validation and serialization coverage.
- Create: `backend/tests/test_news_relevance_dataset.py`
  Purpose: dataset loading, dedupe, batch handling, and benchmark eligibility tests.
- Create: `backend/tests/test_news_relevance_annotation.py`
  Purpose: annotation prompt/parse/error-path tests.
- Create: `backend/tests/test_news_relevance_evaluator.py`
  Purpose: metric calculation, guardrail, and artifact generation tests.
- Create: `backend/tests/test_news_relevance_experiment_runner.py`
  Purpose: scope guard, baseline comparison, and ledger append tests.
- Create: `backend/data/research/market_relevance_candidates.jsonl`
  Purpose: candidate sample pool before review.
- Create: `backend/data/research/market_relevance_benchmark.jsonl`
  Purpose: reviewed benchmark set used for offline evaluation.
- Create: `docs/research/market-relevance-experiments.tsv`
  Purpose: append-only experiment ledger.
- Modify: `backend/app/services/news_ingestion.py`
  Purpose: expose reusable normalization/filter hooks needed by the evaluator and future experiments without widening unrelated scope.
- Modify: `backend/app/services/news_signal_pipeline.py`
  Purpose: expose relevance decision points or classifier integration points needed by the evaluator and experiment runner.
- Modify: `docs/code-change-log.md`
  Purpose: record each completed implementation unit.

## Chunk 1: Dataset And Annotation Foundation

### Task 1: Define research schemas and storage contract

**Files:**
- Create: `backend/app/schemas/research.py`
- Create: `backend/tests/test_research_schemas.py`
- Test: `backend/tests/test_research_schemas.py`

- [ ] **Step 1: Write the failing schema tests**

```python
def test_market_relevance_annotation_requires_noise_type_for_negative():
    with pytest.raises(ValidationError):
        MarketRelevanceLabel(market_relevant=False, noise_type=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_research_schemas.py -q`
Expected: FAIL because `research.py` does not exist yet.

- [ ] **Step 3: Write minimal schemas**

Implement sample, label, annotation metadata, evaluation summary, and experiment ledger models in `backend/app/schemas/research.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_research_schemas.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/research.py backend/tests/test_research_schemas.py
git commit -m "feat: add market relevance research schemas"
```

### Task 2: Build dataset load/save helpers

**Files:**
- Create: `backend/app/services/news_relevance_dataset.py`
- Create: `backend/tests/test_news_relevance_dataset.py`
- Test: `backend/tests/test_news_relevance_dataset.py`

- [ ] **Step 1: Write the failing dataset tests**

```python
def test_benchmark_loader_rejects_model_only_labels():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py -q`
Expected: FAIL because the dataset helper is missing.

- [ ] **Step 3: Write minimal implementation**

Implement JSONL read/write helpers, `sample_id` uniqueness checks, canonical URL dedupe, and a benchmark-only filter that admits only `human_reviewed` and `human_corrected`.

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/news_relevance_dataset.py backend/tests/test_news_relevance_dataset.py
git commit -m "feat: add market relevance dataset helpers"
```

### Task 3: Add historical and realtime sampling script

**Files:**
- Create: `backend/scripts/sample_market_relevance_dataset.py`
- Modify: `backend/app/services/news_ingestion.py`
- Modify: `backend/tests/test_news_ingestion.py`
- Modify: `backend/tests/test_news_relevance_dataset.py`

- [ ] **Step 1: Write the failing tests for sample composition**

```python
def test_sampling_script_preserves_historical_and_realtime_mix():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py backend/tests/test_news_ingestion.py -q`
Expected: FAIL because the sampling script and any required helper hooks do not exist.

- [ ] **Step 3: Write minimal implementation**

Add a script that:
- samples roughly 240 historical rows from `news_item`
- samples roughly 160 realtime candidates from current sources
- dedupes by canonical URL
- writes `backend/data/research/market_relevance_candidates.jsonl`

Only add helper functions to `news_ingestion.py` if the script cannot reuse existing normalization logic cleanly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py backend/tests/test_news_ingestion.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/sample_market_relevance_dataset.py backend/app/services/news_ingestion.py backend/tests/test_news_ingestion.py backend/tests/test_news_relevance_dataset.py backend/data/research/market_relevance_candidates.jsonl
git commit -m "feat: add market relevance dataset sampling"
```

### Task 4: Add first-pass DeepSeek annotation service and script

**Files:**
- Create: `backend/app/services/news_relevance_annotation.py`
- Create: `backend/scripts/annotate_market_relevance.py`
- Create: `backend/tests/test_news_relevance_annotation.py`
- Modify: `backend/app/services/llm_providers.py` (only if JSON helper reuse is needed)

- [ ] **Step 1: Write the failing annotation tests**

```python
def test_annotation_service_parses_market_relevance_schema():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_annotation.py -q`
Expected: FAIL because the annotation service is missing.

- [ ] **Step 3: Write minimal implementation**

Implement:
- a strict prompt for `market_relevant`, `noise_type`, `confidence`, `reason`
- OpenAI-compatible provider invocation through existing config patterns
- parse/validation/error handling
- a script that reads candidates and writes model-first annotations back to JSONL

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_annotation.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/news_relevance_annotation.py backend/scripts/annotate_market_relevance.py backend/tests/test_news_relevance_annotation.py
git commit -m "feat: add market relevance annotation pipeline"
```

## Chunk 2: Review And Offline Evaluation

### Task 5: Add mandatory-review merge workflow

**Files:**
- Create: `backend/scripts/review_market_relevance_annotations.py`
- Modify: `backend/app/services/news_relevance_dataset.py`
- Modify: `backend/tests/test_news_relevance_dataset.py`

- [ ] **Step 1: Write the failing review workflow tests**

```python
def test_review_merge_only_promotes_reviewed_rows_to_benchmark():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py -q`
Expected: FAIL because review merge behavior is not implemented.

- [ ] **Step 3: Write minimal implementation**

Implement review selection rules:
- mandatory review for low confidence, `other`, short or empty-content rows
- random spot-check buckets for high-confidence positives and negatives
- merge reviewed output into `backend/data/research/market_relevance_benchmark.jsonl`

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_dataset.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/review_market_relevance_annotations.py backend/app/services/news_relevance_dataset.py backend/tests/test_news_relevance_dataset.py backend/data/research/market_relevance_benchmark.jsonl
git commit -m "feat: add market relevance review workflow"
```

### Task 6: Implement offline evaluator with guardrails

**Files:**
- Create: `backend/app/services/news_relevance_evaluator.py`
- Create: `backend/scripts/evaluate_market_relevance.py`
- Create: `backend/tests/test_news_relevance_evaluator.py`
- Modify: `backend/app/services/news_signal_pipeline.py`

- [ ] **Step 1: Write the failing evaluator tests**

```python
def test_evaluator_reports_precision_recall_and_noise_rejection():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -q`
Expected: FAIL because the evaluator does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- scoring against benchmark labels
- baseline artifact generation in JSON and Markdown
- guardrails for minimum recall and remaining-kept-rate
- a thin adaptation layer that calls current ingestion/signal relevance logic without changing unrelated behavior

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_evaluator.py -q`
Expected: PASS

- [ ] **Step 5: Run focused integration tests**

Run: `conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_news_ingestion.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/news_relevance_evaluator.py backend/scripts/evaluate_market_relevance.py backend/tests/test_news_relevance_evaluator.py backend/app/services/news_signal_pipeline.py
git commit -m "feat: add market relevance evaluator"
```

### Task 7: Capture baseline and document research operator flow

**Files:**
- Modify: `docs/research/market-relevance-experiments.tsv`
- Modify: `README.md`
- Modify: `docs/code-change-log.md`

- [ ] **Step 1: Add a baseline row format test or fixture**

If no automated test is warranted, add a lightweight schema validation utility and test it.

- [ ] **Step 2: Record the first baseline**

Run: `conda run -n news-caught python backend/scripts/evaluate_market_relevance.py --dataset backend/data/research/market_relevance_benchmark.jsonl --output-dir artifacts/research/baseline`
Expected: baseline artifacts are created and a `baseline` row is appended to the TSV ledger.

- [ ] **Step 3: Document the operator flow**

Update project docs with the exact sequence:
- sample
- annotate
- review
- evaluate baseline

- [ ] **Step 4: Commit**

```bash
git add docs/research/market-relevance-experiments.tsv README.md docs/code-change-log.md
git commit -m "docs: record market relevance baseline workflow"
```

## Chunk 3: Constrained Research Runner

### Task 8: Implement experiment ledger and scope guard

**Files:**
- Create: `backend/app/services/news_relevance_experiment_runner.py`
- Create: `backend/tests/test_news_relevance_experiment_runner.py`
- Modify: `backend/app/schemas/research.py`

- [ ] **Step 1: Write the failing runner tests**

```python
def test_experiment_runner_rejects_changes_outside_allowed_paths():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_experiment_runner.py -q`
Expected: FAIL because the runner is missing.

- [ ] **Step 3: Write minimal implementation**

Implement:
- allowed path whitelist
- ledger append helper
- baseline/result comparison logic
- keep/reject decision payload

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_experiment_runner.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/news_relevance_experiment_runner.py backend/tests/test_news_relevance_experiment_runner.py backend/app/schemas/research.py
git commit -m "feat: add constrained experiment runner"
```

### Task 9: Add single-experiment CLI wrapper

**Files:**
- Create: `backend/scripts/run_news_relevance_experiment.py`
- Modify: `backend/app/services/news_relevance_experiment_runner.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing CLI wrapper tests**

```python
def test_experiment_cli_emits_reject_when_metrics_regress():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_experiment_runner.py -q`
Expected: FAIL because the CLI wrapper is not implemented.

- [ ] **Step 3: Write minimal implementation**

The script should:
- accept one hypothesis string
- accept one patch/apply target or repo state
- run evaluator against the benchmark
- compare to baseline
- append a ledger row
- emit `keep` or `reject`

Do not implement unattended loops or scheduling in this task.

- [ ] **Step 4: Run tests to verify they pass**

Run: `conda run -n news-caught pytest backend/tests/test_news_relevance_experiment_runner.py -q`
Expected: PASS

- [ ] **Step 5: Run end-to-end focused verification**

Run: `conda run -n news-caught pytest backend/tests/test_research_schemas.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_annotation.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/run_news_relevance_experiment.py backend/app/services/news_relevance_experiment_runner.py README.md
git commit -m "feat: add news relevance experiment cli"
```

### Task 10: Final verification and records

**Files:**
- Modify: `docs/code-change-log.md`
- Modify: any touched files above

- [ ] **Step 1: Run backend regression coverage**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py backend/tests/test_news_signal_pipeline.py backend/tests/test_research_schemas.py backend/tests/test_news_relevance_dataset.py backend/tests/test_news_relevance_annotation.py backend/tests/test_news_relevance_evaluator.py backend/tests/test_news_relevance_experiment_runner.py -q`
Expected: PASS

- [ ] **Step 2: Run broad backend suite**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: PASS or only known pre-existing failures with evidence recorded.

- [ ] **Step 3: Update change log**

Append a final summary row in `docs/code-change-log.md` covering dataset tooling, evaluation tooling, and constrained experiment runner verification.

- [ ] **Step 4: Commit**

```bash
git add docs/code-change-log.md
git commit -m "chore: finalize market relevance autoresearch tooling"
```
