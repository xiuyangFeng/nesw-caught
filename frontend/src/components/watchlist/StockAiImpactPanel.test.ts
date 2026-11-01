import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { StockImpact } from '../../types/api';

const { getStockImpacts } = vi.hoisted(() => ({
  getStockImpacts: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  apiClient: { getStockImpacts },
}));

import StockAiImpactPanel from './StockAiImpactPanel.vue';

function buildImpact(overrides: Partial<StockImpact> = {}): StockImpact {
  return {
    news_id: 101,
    news_title: 'Fed cuts rates by 50bp',
    title_zh: '美联储降息 50 个基点',
    published_at: '2026-11-01T02:00:00Z',
    direction: 'bullish',
    strength: 'strong',
    rationale: '流动性宽松',
    source: 'ai',
    view: null,
    ...overrides,
  };
}

function mountPanel(symbol = '600519.SH') {
  return mount(StockAiImpactPanel, {
    props: { symbol },
    global: { stubs: { RouterLink: RouterLinkStub } },
  });
}

describe('StockAiImpactPanel', () => {
  beforeEach(() => {
    getStockImpacts.mockReset();
  });

  it('shows the empty state', async () => {
    getStockImpacts.mockResolvedValue({ data: [], degraded: false });
    const wrapper = mountPanel();
    await flushPromises();

    expect(getStockImpacts).toHaveBeenCalledWith('600519.SH');
    expect(wrapper.get('[data-role="stock-ai-impacts-empty"]').text()).toBe('暂无 AI 影响判断');
  });

  it('lists impacts with chip, linked title, rationale and corrected tag', async () => {
    getStockImpacts.mockResolvedValue({
      data: [
        buildImpact(),
        buildImpact({
          news_id: 102,
          title_zh: null,
          news_title: '茅台提价公告',
          direction: 'bearish',
          strength: 'medium',
          rationale: '短期压制需求',
          source: 'user',
        }),
      ],
      degraded: false,
    });
    const wrapper = mountPanel();
    await flushPromises();

    const rows = wrapper.findAll('[data-role="stock-ai-impact-row"]');
    expect(rows).toHaveLength(2);
    expect(rows[0].get('[data-role="stock-ai-impact-chip"]').text()).toBe('利多·强');
    expect(rows[0].get('[data-role="stock-ai-impact-chip"]').classes()).toContain('text-positive');
    expect(rows[0].text()).toContain('美联储降息 50 个基点');
    expect(rows[0].text()).toContain('流动性宽松');
    expect(rows[0].find('[data-role="stock-ai-impact-corrected"]').exists()).toBe(false);

    expect(rows[1].get('[data-role="stock-ai-impact-chip"]').text()).toBe('利空·中');
    expect(rows[1].text()).toContain('茅台提价公告');
    expect(rows[1].find('[data-role="stock-ai-impact-corrected"]').exists()).toBe(true);

    const targets = wrapper.findAllComponents(RouterLinkStub).map((link) => link.props('to'));
    expect(targets).toEqual(['/news/101', '/news/102']);
  });

  it('reloads when the symbol changes', async () => {
    getStockImpacts.mockResolvedValue({ data: [], degraded: false });
    const wrapper = mountPanel('AAPL');
    await flushPromises();
    await wrapper.setProps({ symbol: 'MSFT' });
    await flushPromises();

    expect(getStockImpacts).toHaveBeenLastCalledWith('MSFT');
  });
});
