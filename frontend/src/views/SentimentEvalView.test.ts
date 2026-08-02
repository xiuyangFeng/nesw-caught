import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { SentimentEvalResponse } from '../types/api';
import SentimentEvalView from './SentimentEvalView.vue';

const { getSentimentEval, runSentimentEval } = vi.hoisted(() => ({
  getSentimentEval: vi.fn(),
  runSentimentEval: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: {
    getSentimentEval,
    runSentimentEval,
  },
}));

const routerLinkStub = {
  props: ['to'],
  template: '<a :href="typeof to === \'string\' ? to : to?.path"><slot /></a>',
};

const ruleRun = {
  model_name: 'rule-baseline',
  metrics: {
    accuracy: 0.7,
    macro_f1: 0.68,
    sample_count: 120,
    per_label: [
      { label: 'positive' as const, precision: 0.72, recall: 0.68, f1: 0.7, support: 40 },
      { label: 'negative' as const, precision: 0.66, recall: 0.64, f1: 0.65, support: 40 },
      { label: 'neutral' as const, precision: 0.69, recall: 0.71, f1: 0.7, support: 40 },
    ],
    confusion_matrix: {
      positive: { positive: 32, negative: 4, neutral: 4 },
      negative: { positive: 3, negative: 30, neutral: 7 },
      neutral: { positive: 2, negative: 5, neutral: 33 },
    },
  },
};

const llmRun = {
  model_name: 'llm:deepseek/deepseek-chat',
  metrics: {
    accuracy: 0.82,
    macro_f1: 0.79,
    sample_count: 120,
    per_label: [],
    confusion_matrix: {},
    importance_weighted_accuracy: 0.83,
  },
};

const response: SentimentEvalResponse = {
  available: true,
  dataset_path: 'data/gold/sentiment.jsonl',
  sample_count: 120,
  primary: ruleRun,
  runs: [ruleRun, llmRun],
  llm_available: true,
  comparison: {
    model_a: ruleRun,
    model_b: llmRun,
    accuracy_delta: 0.12,
    macro_f1_delta: 0.11,
    label_deltas: [
      { label: 'positive', f1_before: 0.7, f1_after: 0.82, f1_delta: 0.12 },
      { label: 'negative', f1_before: 0.65, f1_after: 0.76, f1_delta: 0.11 },
      { label: 'neutral', f1_before: 0.69, f1_after: 0.81, f1_delta: 0.12 },
    ],
    winner: 'model_b',
    reason: 'Model B 在全部标签上均领先。',
  },
  note: null,
  evaluated_at: '2026-08-02T03:00:00Z',
  history: [
    {
      batch_id: 'batch-0002',
      evaluated_at: '2026-08-02T03:00:00Z',
      dataset_hash: 'abc123',
      sample_count: 120,
      entries: [
        { model_name: 'rule-baseline', accuracy: 0.7, macro_f1: 0.68 },
        { model_name: 'llm:deepseek/deepseek-chat', accuracy: 0.82, macro_f1: 0.79 },
      ],
    },
    {
      batch_id: 'batch-0001',
      evaluated_at: '2026-08-01T03:00:00Z',
      dataset_hash: 'abc123',
      sample_count: 120,
      entries: [
        { model_name: 'rule-baseline', accuracy: 0.68, macro_f1: 0.66 },
        { model_name: 'llm:deepseek/deepseek-chat', accuracy: 0.85, macro_f1: 0.83 },
      ],
    },
  ],
  regression: null,
};

describe('SentimentEvalView', () => {
  beforeEach(() => {
    getSentimentEval.mockReset();
    runSentimentEval.mockReset();
    getSentimentEval.mockResolvedValue({ data: response, degraded: false });
    runSentimentEval.mockResolvedValue({ data: response, degraded: false });
  });

  it('loads via GET on mount and renders hero metrics, run cards, per-label table, confusion matrix, A/B and history', async () => {
    const wrapper = mount(SentimentEvalView, { global: { stubs: { RouterLink: routerLinkStub } } });
    await flushPromises();

    expect(getSentimentEval).toHaveBeenCalledTimes(1);
    expect(runSentimentEval).not.toHaveBeenCalled();

    expect(wrapper.find('[data-role="sentiment-eval-hero"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('70.0%');
    expect(wrapper.text()).toContain('68.0%');
    expect(wrapper.text()).toContain('120');
    expect(wrapper.text()).toContain('Model B');

    expect(wrapper.find('[data-role="sentiment-eval-runs"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('rule-baseline');
    expect(wrapper.text()).toContain('llm:deepseek/deepseek-chat');

    expect(wrapper.find('[data-role="sentiment-eval-per-label"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('利好 Positive');
    expect(wrapper.text()).toContain('利空 Negative');
    expect(wrapper.text()).toContain('中性 Neutral');

    expect(wrapper.find('[data-role="sentiment-eval-confusion"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="sentiment-eval-ab"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Winner');

    expect(wrapper.find('[data-role="sentiment-eval-history"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('batch-0002');
    expect(wrapper.text()).toContain('batch-0001');

    expect(wrapper.find('[data-role="sentiment-eval-llm-unavailable"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="sentiment-eval-regression"]').exists()).toBe(false);
  });

  it('shows the unavailable-dataset note when the eval dataset is missing', async () => {
    getSentimentEval.mockResolvedValue({
      data: {
        available: false,
        dataset_path: 'data/gold/sentiment.jsonl',
        sample_count: 0,
        primary: null,
        comparison: null,
        note: '金标数据集文件不存在。',
      },
      degraded: false,
    });

    const wrapper = mount(SentimentEvalView, { global: { stubs: { RouterLink: routerLinkStub } } });
    await flushPromises();

    expect(wrapper.find('[data-role="sentiment-eval-unavailable"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('金标数据集文件不存在。');
    expect(wrapper.text()).toContain('data/gold/sentiment.jsonl');
    expect(wrapper.find('[data-role="sentiment-eval-hero"]').exists()).toBe(false);
  });

  it('shows an error message and does not crash when the eval API fails', async () => {
    getSentimentEval.mockRejectedValue(new Error('评测服务异常'));

    const wrapper = mount(SentimentEvalView, { global: { stubs: { RouterLink: routerLinkStub } } });
    await flushPromises();

    expect(wrapper.find('[data-role="sentiment-eval-error"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('评测服务异常');
    expect(wrapper.find('[data-role="sentiment-eval-hero"]').exists()).toBe(false);
  });

  it('triggers POST /api/eval/sentiment/run then refreshes via GET when clicking 重新评测', async () => {
    const wrapper = mount(SentimentEvalView, { global: { stubs: { RouterLink: routerLinkStub } } });
    await flushPromises();
    expect(getSentimentEval).toHaveBeenCalledTimes(1);

    await wrapper.get('[data-role="sentiment-eval-rerun"]').trigger('click');
    await flushPromises();

    expect(runSentimentEval).toHaveBeenCalledTimes(1);
    expect(getSentimentEval).toHaveBeenCalledTimes(2);
  });

  it('renders a red regression badge with model name and macro_f1 delta when regressed', async () => {
    getSentimentEval.mockResolvedValue({
      data: {
        ...response,
        regression: {
          model_name: 'llm:deepseek/deepseek-chat',
          previous_macro_f1: 0.86,
          current_macro_f1: 0.79,
          delta: -0.07,
          regressed: true,
        },
      },
      degraded: false,
    });

    const wrapper = mount(SentimentEvalView, { global: { stubs: { RouterLink: routerLinkStub } } });
    await flushPromises();

    const badge = wrapper.find('[data-role="sentiment-eval-regression"]');
    expect(badge.exists()).toBe(true);
    expect(badge.text()).toContain('llm:deepseek/deepseek-chat');
    expect(badge.text()).toContain('-0.0700');
  });

  it('shows the LLM-not-configured hint with a link to /settings/llm when llm_available is false', async () => {
    getSentimentEval.mockResolvedValue({
      data: {
        ...response,
        llm_available: false,
        runs: [ruleRun],
        note: '未配置 LLM，仅规则阈值对比。',
      },
      degraded: false,
    });

    const wrapper = mount(SentimentEvalView, { global: { stubs: { RouterLink: routerLinkStub } } });
    await flushPromises();

    const hint = wrapper.find('[data-role="sentiment-eval-llm-unavailable"]');
    expect(hint.exists()).toBe(true);
    expect(hint.text()).toContain('未配置 LLM');
    const link = hint.find('a');
    expect(link.exists()).toBe(true);
    expect(link.attributes('href')).toBe('/settings/llm');
  });

  it('shows a guided empty state when available=true but primary=null (no eval runs yet)', async () => {
    getSentimentEval.mockResolvedValue({
      data: {
        available: true,
        dataset_path: 'data/gold/sentiment.jsonl',
        sample_count: 120,
        primary: null,
        runs: [],
        llm_available: true,
        comparison: null,
        note: '尚无评测记录，请点击重新评测。',
        evaluated_at: null,
        history: [],
        regression: null,
      },
      degraded: false,
    });

    const wrapper = mount(SentimentEvalView, { global: { stubs: { RouterLink: routerLinkStub } } });
    await flushPromises();

    expect(wrapper.find('[data-role="sentiment-eval-no-runs"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('尚无评测记录');
    expect(wrapper.find('[data-role="sentiment-eval-hero"]').exists()).toBe(false);
  });
});
