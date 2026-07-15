import { flushPromises, mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Digest } from '../types/api';
import DigestView from './DigestView.vue';

const digest: Digest = {
  generated_at: '2026-07-14T00:10:00Z',
  generated_by: 'llm',
  market_scope: 'all',
  model_name: 'deepseek-chat',
  sections: [
    { title: '隔夜要闻', body: '- 美股全线上涨\n- 科技股领涨' },
    { title: '情绪方向', body: '整体情绪偏多头。' },
  ],
  title: '7月14日盘前简报',
};

const digestStore = reactive({
  digest: null as Digest | null,
  available: false,
  loading: false,
  generating: false,
  error: null as string | null,
  marketScope: 'all' as 'all' | 'hk' | 'us',
  loadLatest: vi.fn(async () => undefined),
  generate: vi.fn(async () => undefined),
});

vi.mock('../stores/digestStore', () => ({
  useDigestStore: () => digestStore,
}));

describe('DigestView', () => {
  beforeEach(() => {
    digestStore.digest = null;
    digestStore.available = false;
    digestStore.loading = false;
    digestStore.generating = false;
    digestStore.error = null;
    digestStore.marketScope = 'all';
    digestStore.loadLatest.mockClear();
    digestStore.generate.mockClear();
  });

  it('loads and renders the latest digest sections', async () => {
    digestStore.digest = digest;
    digestStore.available = true;

    const wrapper = mount(DigestView);
    await flushPromises();

    expect(digestStore.loadLatest).toHaveBeenCalled();
    expect(wrapper.find('[data-role="digest-card"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('7月14日盘前简报');
    expect(wrapper.text()).toContain('LLM 生成');
    expect(wrapper.text()).toContain('隔夜要闻');
    expect(wrapper.text()).toContain('美股全线上涨');
    expect(wrapper.text()).toContain('情绪方向');
  });

  it('shows the empty state when there is no digest yet', async () => {
    const wrapper = mount(DigestView);
    await flushPromises();

    expect(wrapper.text()).toContain('暂无简报');
    expect(wrapper.text()).toContain('尚未生成任何简报');
  });

  it('shows a loading message while the first fetch is in flight', () => {
    digestStore.loading = true;

    const wrapper = mount(DigestView);

    expect(wrapper.text()).toContain('正在加载最新简报…');
  });

  it('shows an error message without crashing when generation fails', () => {
    digestStore.error = '生成简报失败：模型超时';

    const wrapper = mount(DigestView);

    expect(wrapper.text()).toContain('生成简报失败：模型超时');
  });

  it('switches market scope when a market tab is clicked', async () => {
    const wrapper = mount(DigestView);
    await flushPromises();

    const tabs = wrapper.findAll('[data-role="digest-market-tabs"] button');
    expect(tabs.map((t) => t.text())).toEqual(['全市场', '港股', '美股']);

    await tabs[1].trigger('click');

    expect(digestStore.marketScope).toBe('hk');
  });

  it('triggers digest generation when the generate button is clicked', async () => {
    const wrapper = mount(DigestView);
    await flushPromises();

    await wrapper.get('[data-role="digest-generate-button"]').trigger('click');
    await flushPromises();

    expect(digestStore.generate).toHaveBeenCalledTimes(1);
  });

  it('does not crash when generate() rejects', async () => {
    digestStore.generate.mockRejectedValueOnce(new Error('生成失败'));
    const wrapper = mount(DigestView);
    await flushPromises();

    await wrapper.get('[data-role="digest-generate-button"]').trigger('click');
    await flushPromises();

    expect(digestStore.generate).toHaveBeenCalledTimes(1);
  });
});
