# Market Relevance Recall Merge Design

## Goal

Merge the two lowest-risk recall improvements from the automation worktrees into `main`: the concept-mover heuristic and the shipping-route disruption heuristic.

## Scope

- Keep the existing `index-signals` behavior unchanged.
- Add one narrow Chinese concept-mover rule for market headlines that combine concept-sector language with explicit equity move language.
- Add one narrow shipping disruption rule for English headlines that combine shipping actors with route disruption phrases.
- Regenerate the combined evaluation artifact, ledger entry, and morning report from `main`.

## Non-Goals

- Do not merge the `sector-move-signals` branch that removes broad shareholder heuristics.
- Do not broaden geopolitical relevance rules.
- Do not resample the benchmark or modify reviewed labels.

## Approach

Start from the current `main` evaluator. Add focused tests for the two desired behaviors plus their negative guardrails, verify they fail on `main`, then add the minimal heuristics needed to make them pass. After that, run the benchmark evaluation into a new combined artifact directory, record a new keep experiment in the ledger, refresh the report, and update the code change log.

## Expected Outcome

The combined evaluator should preserve the existing precision guardrail while lifting recall above the current `index-signals` result. Based on the separate worktree experiments, the expected target is at least `precision=0.8235`, `recall=0.8824`, and `noise_rejection_rate=0.9286` if the two improvements stack cleanly.
