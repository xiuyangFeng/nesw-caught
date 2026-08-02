"""离线跑一遍情绪评测并渲染 Markdown 报告（盘活此前全文件死代码的 news_sentiment_report.py）。

用法：
    python scripts/run_sentiment_experiment.py
    python scripts/run_sentiment_experiment.py --dataset data/research/sentiment_gold_benchmark.json
    python scripts/run_sentiment_experiment.py --with-llm

始终评一遍 rule-baseline（±0.20 阈值，title+summary+body 全量输入，离线确定性可
复现，不依赖数据库里的 LLM 配置）。加 --with-llm 时额外用当前激活的 LLM provider
配置（DB 里 is_active=True 的那条）评一遍 `llm:<provider>/<model>` 并生成 A/B 对比；
没有激活配置时打印提示并跳过（不报错退出）。

报告写到 backend/data/research/experiments/sentiment/<YYYY-MM-DD>/report.md
（可用 --output-dir 覆盖）。
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.services.news_sentiment_dataset import default_gold_dataset_path, load_gold_samples
from app.services.news_sentiment_evaluator import build_rule_sentiment_classifier
from app.services.news_sentiment_experiment_runner import (
    compare_sentiment_runs,
    run_sentiment_evaluation,
)
from app.services.news_sentiment_llm_classifier import NewsSentimentLLMClassifier
from app.services.news_sentiment_report import (
    build_sentiment_report,
    render_sentiment_report_markdown,
)
from app.services.news_signal_classifier import NewsSignalClassifier


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an offline sentiment eval pass and render a markdown report."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Path to gold dataset JSON (default: built-in demo set at "
        "backend/data/research/sentiment_gold_benchmark.json)",
    )
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Also evaluate llm:<provider>/<model> against the currently active LLM "
        "provider config and include an A/B comparison against rule-baseline",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override output directory (default: "
        "backend/data/research/experiments/sentiment/<YYYY-MM-DD>)",
    )
    args = parser.parse_args()

    dataset_path = args.dataset or default_gold_dataset_path()
    samples = load_gold_samples(dataset_path)
    if not samples:
        print(f"no gold samples found at {dataset_path}", file=sys.stderr)
        raise SystemExit(1)

    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        rule_fn = build_rule_sentiment_classifier(
            classifier, positive_threshold=0.2, negative_threshold=-0.2
        )
        rule_run = run_sentiment_evaluation(samples, model_name="rule-baseline", classify_fn=rule_fn)

        comparison = None
        if args.with_llm:
            active_config = LLMProviderConfigRepository(session).get_active()
            if active_config is None:
                print(
                    "--with-llm requested but no active LLM provider config found; "
                    "skipping llm run, reporting rule-baseline only",
                    file=sys.stderr,
                )
            else:
                model_label = f"{active_config.provider_name}/{active_config.model_name}"
                llm_classifier = NewsSentimentLLMClassifier(config=active_config, rule_fallback=rule_fn)
                llm_run = run_sentiment_evaluation(
                    samples, model_name=f"llm:{model_label}", classify_fn=llm_classifier.classify
                )
                comparison = compare_sentiment_runs(rule_run, llm_run)
                if llm_classifier.fallback_count:
                    print(
                        f"llm classification fell back to rule baseline for "
                        f"{llm_classifier.fallback_count}/{llm_classifier.call_count} samples",
                        file=sys.stderr,
                    )

    report = build_sentiment_report(rule_run, comparison)
    markdown = render_sentiment_report_markdown(report)

    output_dir = args.output_dir or (
        Path(__file__).resolve().parents[1]
        / "data"
        / "research"
        / "experiments"
        / "sentiment"
        / datetime.now(UTC).strftime("%Y-%m-%d")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.md"
    report_path.write_text(markdown, encoding="utf-8")
    print(f"wrote {report_path}")


if __name__ == "__main__":
    main()
