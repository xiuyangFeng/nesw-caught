import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { MarketOverviewMarket } from '../../types/api';
import MarketOverviewCard from './MarketOverviewCard.vue';

const push = vi.fn();

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}));

function buildMarket(overrides: Record<string, unknown> = {}): MarketOverviewMarket {
  return {
    market: 'us',
    display_name: '美股',
    is_open: true,
    indices: [
      {
        symbol: '^GSPC',
        display_name: '标普500',
        kind: 'index',
        price: 6450.12,
        change_percent: 0.82,
        previous_close: 6397.6,
        status: 'ok',
        fetched_at: '2026-08-02T08:00:00Z',
      },
      {
        symbol: '^IXIC',
        display_name: '纳斯达克',
        kind: 'index',
        price: 21480.55,
        change_percent: -0.35,
        previous_close: 21556.0,
        status: 'ok',
        fetched_at: '2026-08-02T08:00:00Z',
      },
    ],
    quant_sentiment: {
      score: 0.45,
      label: 'greed',
      inputs: { avg_change_percent: 0.24, vix: 14.2, adv_ratio: null },
    },
    boards: {
      status: 'ok',
      stale: false,
      source: 'preset_etf',
      items: [
        { code: 'XLK', name: '科技ETF', change_percent: 1.2 },
        { code: 'XLE', name: '能源ETF', change_percent: -0.6 },
      ],
    },
    news_sentiment: {
      status: 'ok',
      score: 0.31,
      sample_count: 12,
      top_signals: [
        {
          news_id: 101,
          title: 'Fed officials signal patience on rate path',
          summary: '多位美联储官员暗示不急于调整利率路径。',
          signal_confidence: 0.9,
          source_name: 'Reuters',
          published_at: '2026-08-02T06:30:00Z',
          canonical_url: 'https://example.com/news/101',
        },
      ],
    },
    ...overrides,
  } as MarketOverviewMarket;
}

function mountCard(data: MarketOverviewMarket) {
  return mount(MarketOverviewCard, { props: { data } });
}

describe('MarketOverviewCard', () => {
  beforeEach(() => {
    push.mockClear();
  });

  it('renders market name, open badge and index rows with change colors', () => {
    const wrapper = mountCard(buildMarket());

    expect(wrapper.get('[data-role="market-overview-card-us"]').text()).toContain('美股');
    expect(wrapper.get('[data-role="market-open-badge"]').text()).toContain('开盘中');
    const upRow = wrapper.get('[data-role="overview-index-^GSPC"]');
    expect(upRow.text()).toContain('标普500');
    expect(upRow.find('[data-role="overview-index-change"]').classes()).toContain('text-positive');
    const downRow = wrapper.get('[data-role="overview-index-^IXIC"]');
    expect(downRow.find('[data-role="overview-index-change"]').classes()).toContain('text-negative');
  });

  it('shows the closed badge when the market is not open', () => {
    const wrapper = mountCard(buildMarket({ is_open: false }));

    expect(wrapper.get('[data-role="market-open-badge"]').text()).toContain('已闭市');
  });

  it('hides the ^VIX row from the index list', () => {
    const wrapper = mountCard(
      buildMarket({
        indices: [
          {
            symbol: '^VIX',
            display_name: '恐慌指数',
            kind: 'index',
            price: 14.2,
            change_percent: -2.1,
            previous_close: 14.5,
            status: 'ok',
            fetched_at: '2026-08-02T08:00:00Z',
          },
          ...buildMarket().indices,
        ],
      }),
    );

    expect(wrapper.find('[data-role="overview-index-^VIX"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="overview-index-^GSPC"]').exists()).toBe(true);
  });

  it('maps quant sentiment labels to chips with copy', () => {
    const cases: Array<[string, string]> = [
      ['panic', '恐慌'],
      ['fear', '偏慌'],
      ['neutral', '中性'],
      ['greed', '贪婪'],
      ['greed_extreme', '极度贪婪'],
      ['unknown', '数据不足'],
    ];
    for (const [label, text] of cases) {
      const wrapper = mountCard(
        buildMarket({ quant_sentiment: { score: null, label, inputs: null } }),
      );
      expect(wrapper.get('[data-role="quant-sentiment-chip"]').text()).toContain(text);
    }
  });

  it('falls back to the unknown chip when quant sentiment is missing', () => {
    const wrapper = mountCard(buildMarket({ quant_sentiment: null }));

    expect(wrapper.get('[data-role="quant-sentiment-chip"]').text()).toContain('数据不足');
  });

  it('renders eastmoney board rankings for cn markets', () => {
    const wrapper = mountCard(
      buildMarket({
        market: 'cn',
        display_name: 'A股',
        boards: {
          status: 'ok',
          stale: false,
          source: 'eastmoney',
          items: [
            { code: 'BK0420', name: '航天航空', change_percent: 2.35 },
            { code: 'BK0475', name: '银行', change_percent: -0.92 },
          ],
        },
      }),
    );

    const section = wrapper.get('[data-role="board-section"]');
    expect(section.text()).toContain('行业板块');
    expect(section.text()).toContain('航天航空');
    expect(section.text()).toContain('+2.35%');
  });

  it('renders the preset ETF list for us/eu markets', () => {
    const wrapper = mountCard(buildMarket());

    const section = wrapper.get('[data-role="board-section"]');
    expect(section.text()).toContain('板块代理');
    expect(section.text()).toContain('科技ETF');
  });

  it('does not render the board section at all when source is none (kr/jp)', () => {
    const wrapper = mountCard(
      buildMarket({
        market: 'kr',
        display_name: '韩国',
        boards: { status: 'none', stale: false, source: 'none', items: [] },
      }),
    );

    expect(wrapper.find('[data-role="board-section"]').exists()).toBe(false);
  });

  it('shows an unavailable hint instead of items when board fetching failed', () => {
    const wrapper = mountCard(
      buildMarket({
        boards: { status: 'fetch_failed', stale: false, source: 'eastmoney', items: [] },
      }),
    );

    expect(wrapper.get('[data-role="board-section"]').text()).toContain('暂不可用');
  });

  it('marks stale board data', () => {
    const wrapper = mountCard(
      buildMarket({
        boards: {
          status: 'ok',
          stale: true,
          source: 'preset_etf',
          items: [{ code: 'XLK', name: '科技ETF', change_percent: 1.2 }],
        },
      }),
    );

    expect(wrapper.get('[data-role="board-section"]').text()).toContain('滞后');
  });

  it('renders news sentiment score and navigates to news detail on signal click', async () => {
    const wrapper = mountCard(buildMarket());

    const section = wrapper.get('[data-role="news-sentiment-section"]');
    expect(section.text()).toContain('0.31');
    expect(section.text()).toContain('Fed officials signal patience on rate path');

    await wrapper.get('[data-role="news-signal-101"]').trigger('click');

    expect(push).toHaveBeenCalledWith({ name: 'news-detail', params: { id: 101 } });
  });

  it('degrades gracefully when news sentiment sample is insufficient', () => {
    const wrapper = mountCard(
      buildMarket({
        news_sentiment: { status: 'insufficient_data', score: null, sample_count: 1, top_signals: [] },
      }),
    );

    expect(wrapper.get('[data-role="news-sentiment-section"]').text()).toContain('样本不足');
    expect(wrapper.find('[data-role^="news-signal-"]').exists()).toBe(false);
  });

  it('degrades gracefully when news sentiment is absent entirely', () => {
    const wrapper = mountCard(buildMarket({ news_sentiment: null }));

    expect(wrapper.get('[data-role="news-sentiment-section"]').text()).toContain('暂无数据');
  });
});
