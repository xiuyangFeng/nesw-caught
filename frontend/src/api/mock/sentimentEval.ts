// 情绪/利好利空评测 (Sentiment Eval Harness) mock 数据：GET /api/eval/sentiment 与
// POST /api/eval/sentiment/run 共用同一份夹具（重新评测在离线模式下返回同一快照）。
//
// 覆盖设计文档 docs/superpowers/specs/2026-08-02-sentiment-eval-revamp-design.md
// 的三个模型 run（rule-baseline / llm / hybrid）、history 走势与 regression 回归对比，
// 便于在后端工作块 B 落地前离线联调前端展示。

import type { SentimentEvalResponse } from '../../types/api';
import { isoMinutesAgo } from './shared';

function metrics(accuracy: number, macroF1: number, importanceWeighted: number | null) {
  return {
    accuracy,
    macro_f1: macroF1,
    sample_count: 120,
    per_label: [
      { label: 'positive' as const, precision: accuracy + 0.02, recall: accuracy - 0.03, f1: macroF1 + 0.01, support: 40 },
      { label: 'negative' as const, precision: accuracy - 0.04, recall: accuracy - 0.01, f1: macroF1 - 0.02, support: 40 },
      { label: 'neutral' as const, precision: accuracy - 0.01, recall: accuracy + 0.02, f1: macroF1 + 0.01, support: 40 },
    ],
    confusion_matrix: {
      positive: { positive: 32, negative: 4, neutral: 4 },
      negative: { positive: 3, negative: 30, neutral: 7 },
      neutral: { positive: 2, negative: 5, neutral: 33 },
    },
    importance_weighted_accuracy: importanceWeighted,
  };
}

const ruleRun = { model_name: 'rule-baseline', metrics: metrics(0.7, 0.68, 0.71) };
const llmRun = { model_name: 'llm:deepseek/deepseek-chat', metrics: metrics(0.85, 0.82, 0.86) };
const hybridRun = { model_name: 'hybrid:deepseek/deepseek-chat', metrics: metrics(0.83, 0.8, 0.84) };

export const mockSentimentEval: SentimentEvalResponse = {
  available: true,
  dataset_path: 'data/gold/sentiment_v2.jsonl',
  sample_count: 120,
  primary: ruleRun,
  runs: [ruleRun, llmRun, hybridRun],
  llm_available: true,
  comparison: {
    model_a: ruleRun,
    model_b: llmRun,
    accuracy_delta: 0.15,
    macro_f1_delta: 0.14,
    label_deltas: [
      { label: 'positive', f1_before: 0.69, f1_after: 0.83, f1_delta: 0.14 },
      { label: 'negative', f1_before: 0.66, f1_after: 0.8, f1_delta: 0.14 },
      { label: 'neutral', f1_before: 0.69, f1_after: 0.83, f1_delta: 0.14 },
    ],
    winner: 'model_b',
    reason: 'llm:deepseek/deepseek-chat 在全部标签上均领先 rule-baseline。',
  },
  note: null,
  evaluated_at: isoMinutesAgo(12),
  history: [
    {
      batch_id: 'batch-mock-0003',
      evaluated_at: isoMinutesAgo(12),
      dataset_hash: 'ab12cd34ef56ab78',
      sample_count: 120,
      entries: [
        { model_name: 'rule-baseline', accuracy: 0.7, macro_f1: 0.68 },
        { model_name: 'llm:deepseek/deepseek-chat', accuracy: 0.85, macro_f1: 0.82 },
        { model_name: 'hybrid:deepseek/deepseek-chat', accuracy: 0.83, macro_f1: 0.8 },
      ],
    },
    {
      batch_id: 'batch-mock-0002',
      evaluated_at: isoMinutesAgo(1500),
      dataset_hash: 'ab12cd34ef56ab78',
      sample_count: 120,
      entries: [
        { model_name: 'rule-baseline', accuracy: 0.69, macro_f1: 0.67 },
        { model_name: 'llm:deepseek/deepseek-chat', accuracy: 0.88, macro_f1: 0.86 },
        { model_name: 'hybrid:deepseek/deepseek-chat', accuracy: 0.84, macro_f1: 0.81 },
      ],
    },
    {
      batch_id: 'batch-mock-0001',
      evaluated_at: isoMinutesAgo(4200),
      dataset_hash: '9f8e7d6c5b4a3210',
      sample_count: 96,
      entries: [
        { model_name: 'rule-baseline', accuracy: 0.66, macro_f1: 0.64 },
        { model_name: 'llm:deepseek/deepseek-chat', accuracy: 0.8, macro_f1: 0.77 },
      ],
    },
  ],
  regression: {
    model_name: 'llm:deepseek/deepseek-chat',
    previous_macro_f1: 0.86,
    current_macro_f1: 0.82,
    delta: -0.04,
    regressed: true,
  },
};

/** 未配置 LLM 时的降级夹具：仅规则阈值 A/B（legacy 行为），无 runs 中的 llm/hybrid。 */
export const mockSentimentEvalNoLlm: SentimentEvalResponse = {
  available: true,
  dataset_path: 'data/gold/sentiment_v2.jsonl',
  sample_count: 120,
  primary: ruleRun,
  runs: [ruleRun],
  llm_available: false,
  comparison: {
    model_a: ruleRun,
    model_b: { model_name: 'rule-sensitive (±0.10)', metrics: metrics(0.72, 0.7, 0.73) },
    accuracy_delta: 0.02,
    macro_f1_delta: 0.02,
    label_deltas: [
      { label: 'positive', f1_before: 0.69, f1_after: 0.71, f1_delta: 0.02 },
      { label: 'negative', f1_before: 0.66, f1_after: 0.68, f1_delta: 0.02 },
      { label: 'neutral', f1_before: 0.69, f1_after: 0.71, f1_delta: 0.02 },
    ],
    winner: 'model_b',
    reason: '未配置 LLM，仅规则阈值对比。',
  },
  note: '未配置 LLM，仅规则阈值对比。',
  evaluated_at: isoMinutesAgo(30),
  history: [],
  regression: null,
};

/** 金标存在但库里无记录时的引导空状态夹具。 */
export const mockSentimentEvalNoRuns: SentimentEvalResponse = {
  available: true,
  dataset_path: 'data/gold/sentiment_v2.jsonl',
  sample_count: 120,
  primary: null,
  runs: [],
  llm_available: true,
  comparison: null,
  note: '尚无评测记录，请点击重新评测。',
  evaluated_at: null,
  history: [],
  regression: null,
};
