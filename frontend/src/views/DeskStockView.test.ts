import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskStockView from './DeskStockView.vue';

const { getQuantResearch, getStockKline, getQuantFundFlow } = vi.hoisted(() => ({
  getQuantResearch: vi.fn(),
  getStockKline: vi.fn(),
  getQuantFundFlow: vi.fn(),
}));

vi.mock('../api/client', () => ({
  apiClient: { getQuantResearch, getStockKline, getQuantFundFlow },
}));

const routeState = { params: { symbol: '600519.SH' } };
const push = vi.fn();

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push }),
}));

// KlineChart 内部依赖 lightweight-charts 操作真实 DOM/canvas，父视图测试只关心接线，
// 渲染行为由 KlineChart.test.ts 自身覆盖（照抄 WatchlistDetailView.test.ts 的做法）。
vi.mock('../components/watchlist/KlineChart.vue', () => ({
  default: {
    props: ['klineData', 'currentPeriod', 'highlightedEventTime'],
    template: '<section data-role="kline-chart-stub">{{ klineData?.symbol }}</section>',
  },
}));

const sampleKline = {
  symbol: '600519.SH',
  interval: '1d',
  range: '1y',
  stale: false,
  candles: [
    { time: '2026-08-14', open: 100, high: 110, low: 95, close: 105, volume: 1000 },
    { time: '2026-08-17', open: 105, high: 112, low: 101, close: 108, volume: 1200 },
  ],
  indicators: { macd: [], kdj: [], bollinger: [] },
  news_events: [],
};

describe('DeskStockView', () => {
  beforeEach(() => {
    routeState.params.symbol = '600519.SH';
    getQuantResearch.mockReset();
    getStockKline.mockReset();
    getQuantFundFlow.mockReset();
    push.mockReset();
    getQuantResearch.mockResolvedValue({
      data: {
        symbol: '600519.SH',
        modules: [
          {
            key: 'valuation',
            question: '估值情景',
            answer: '不给出无依据价格锚',
            evidence_ids: [],
            gap: 'no_financials_or_consensus',
          },
        ],
        ask_ai_context: 'ctx',
      },
      degraded: false,
    });
    getQuantFundFlow.mockResolvedValue({
      data: { symbol: '600519.SH', points: [], note: '尚无个股资金流。' },
      degraded: false,
    });
  });

  it('renders research modules and ask-ai affordance', async () => {
    getStockKline.mockResolvedValue({ data: sampleKline, degraded: false });
    const wrapper = mount(DeskStockView);
    await flushPromises();
    expect(wrapper.find('[data-role="desk-stock-view"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('估值情景');
    expect(wrapper.find('[data-role="desk-ask-ai"]').exists()).toBe(true);
    await wrapper.get('[data-role="desk-ask-ai"]').trigger('click');
    expect(push).toHaveBeenCalledWith({ path: '/chat', query: { desk_symbol: '600519.SH' } });
  });

  it('loads and renders the kline chart on success', async () => {
    getStockKline.mockResolvedValue({ data: sampleKline, degraded: false });
    const wrapper = mount(DeskStockView);
    await flushPromises();

    expect(getStockKline).toHaveBeenCalledWith('600519.SH', '1d', '1y');
    expect(wrapper.find('[data-role="kline-chart-stub"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="desk-kline-empty"]').exists()).toBe(false);
  });

  it('shows an empty state when the kline request fails, without blanking the page', async () => {
    getStockKline.mockRejectedValue(new Error('网络错误'));
    const wrapper = mount(DeskStockView);
    await flushPromises();

    expect(wrapper.find('[data-role="kline-chart-stub"]').exists()).toBe(false);
    const emptyState = wrapper.find('[data-role="desk-kline-empty"]');
    expect(emptyState.exists()).toBe(true);
    expect(emptyState.text()).toContain('K 线数据加载失败');
    // 研究包区域仍然正常渲染，不受 K 线失败影响。
    expect(wrapper.text()).toContain('估值情景');
  });

  it('shows the fund-flow panel for A-share symbols', async () => {
    getStockKline.mockResolvedValue({ data: sampleKline, degraded: false });
    const wrapper = mount(DeskStockView);
    await flushPromises();

    expect(wrapper.find('[data-role="stock-fund-flow"]').exists()).toBe(true);
    expect(getQuantFundFlow).toHaveBeenCalledWith('600519.SH');
  });

  it('hides the fund-flow panel for non A-share symbols', async () => {
    routeState.params.symbol = 'AAPL';
    getStockKline.mockResolvedValue({ data: { ...sampleKline, symbol: 'AAPL' }, degraded: false });
    const wrapper = mount(DeskStockView);
    await flushPromises();

    expect(wrapper.find('[data-role="stock-fund-flow"]').exists()).toBe(false);
    expect(getQuantFundFlow).not.toHaveBeenCalled();
  });
});
