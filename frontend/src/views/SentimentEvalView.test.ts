import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { SentimentEvalResponse } from '../types/api';
import SentimentEvalView from './SentimentEvalView.vue';

const { getSentimentEval } = vi.hoisted(() => ({
  getSentimentEval: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: {
    getSentimentEval,
  },
}));

const response: SentimentEvalResponse = {
  available: true,
  dataset_path: 'data/gold/sentiment.jsonl',
  sample_count: 120,
  primary: {
    model_name: 'deepseek-chat',
    metrics: {
      accuracy: 0.82,
      macro_f1: 0.79,
      sample_count: 120,
      per_label: [
        { label: 'positive', precision: 0.85, recall: 0.8, f1: 0.82, support: 40 },
        { label: 'negative', precision: 0.78, recall: 0.75, f1: 0.76, support: 40 },
        { label: 'neutral', precision: 0.8, recall: 0.83, f1: 0.81, support: 40 },
      ],
      confusion_matrix: {
        positive: { positive: 32, negative: 4, neutral: 4 },
        negative: { positive: 3, negative: 30, neutral: 7 },
        neutral: { positive: 2, negative: 5, neutral: 33 },
      },
    },
  },
  comparison: {
    model_a: {
      model_name: 'rule-based-v1',
      metrics: {
        accuracy: 0.7,
        macro_f1: 0.68,
        sample_count: 120,
        per_label: [],
        confusion_matrix: {},
      },
    },
    model_b: {
      model_name: 'deepseek-chat',
      metrics: {
        accuracy: 0.82,
        macro_f1: 0.79,
        sample_count: 120,
        per_label: [],
        confusion_matrix: {},
      },
    },
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
};

describe('SentimentEvalView', () => {
  beforeEach(() => {
    getSentimentEval.mockReset();
    getSentimentEval.mockResolvedValue({ data: response, degraded: false });
  });

  it('renders hero metrics, per-label table, confusion matrix and A/B comparison', async () => {
    const wrapper = mount(SentimentEvalView);
    await flushPromises();

    expect(getSentimentEval).toHaveBeenCalled();
    expect(wrapper.find('[data-role="sentiment-eval-hero"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('82.0%');
    expect(wrapper.text()).toContain('79.0%');
    expect(wrapper.text()).toContain('120');
    expect(wrapper.text()).toContain('Model B');

    expect(wrapper.find('[data-role="sentiment-eval-per-label"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('利好 Positive');
    expect(wrapper.text()).toContain('利空 Negative');
    expect(wrapper.text()).toContain('中性 Neutral');

    expect(wrapper.find('[data-role="sentiment-eval-confusion"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="sentiment-eval-ab"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('rule-based-v1');
    expect(wrapper.text()).toContain('Winner');
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

    const wrapper = mount(SentimentEvalView);
    await flushPromises();

    expect(wrapper.find('[data-role="sentiment-eval-unavailable"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('金标数据集文件不存在。');
    expect(wrapper.text()).toContain('data/gold/sentiment.jsonl');
    expect(wrapper.find('[data-role="sentiment-eval-hero"]').exists()).toBe(false);
  });

  it('shows an error message and does not crash when the eval API fails', async () => {
    getSentimentEval.mockRejectedValue(new Error('评测服务异常'));

    const wrapper = mount(SentimentEvalView);
    await flushPromises();

    expect(wrapper.find('[data-role="sentiment-eval-error"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('评测服务异常');
    expect(wrapper.find('[data-role="sentiment-eval-hero"]').exists()).toBe(false);
  });

  it('re-runs the evaluation when the re-evaluate button is clicked', async () => {
    const wrapper = mount(SentimentEvalView);
    await flushPromises();
    expect(getSentimentEval).toHaveBeenCalledTimes(1);

    await wrapper.get('button').trigger('click');
    await flushPromises();

    expect(getSentimentEval).toHaveBeenCalledTimes(2);
  });
});
