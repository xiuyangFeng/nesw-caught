import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { WatchlistQuoteSummary } from '../../types/api';
import StockCard from './StockCard.vue';
import WatchlistSidebar from './WatchlistSidebar.vue';

function buildQuote(overrides: Partial<WatchlistQuoteSummary> = {}): WatchlistQuoteSummary {
  return {
    symbol: '688256.SH',
    market: 'cn',
    display_name: '寒武纪',
    price: 106.1,
    change_percent: 6.1,
    status: 'ok',
    fetched_at: '2026-11-02T02:00:00Z',
    has_hot_alert: false,
    ...overrides,
  } as WatchlistQuoteSummary;
}

describe('StockCard holding highlight', () => {
  it('marks holdings with a highlight bar and badge', () => {
    const wrapper = mount(StockCard, {
      props: { row: buildQuote(), selected: false, sparkline: [], deleting: false, holding: true },
    });

    expect(wrapper.get('[data-role="stock-card-688256.SH"]').attributes('data-holding')).toBe('true');
    expect(wrapper.find('[data-role="stock-card-holding-bar"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="stock-card-holding-badge"]').text()).toBe('持仓');
  });

  it('leaves watch-only stocks unmarked', () => {
    const wrapper = mount(StockCard, {
      props: { row: buildQuote(), selected: false, sparkline: [], deleting: false },
    });

    expect(wrapper.get('[data-role="stock-card-688256.SH"]').attributes('data-holding')).toBe('false');
    expect(wrapper.find('[data-role="stock-card-holding-bar"]').exists()).toBe(false);
    expect(wrapper.find('[data-role="stock-card-holding-badge"]').exists()).toBe(false);
  });
});

describe('WatchlistSidebar holdings', () => {
  it('highlights only items with a positive position size', () => {
    const wrapper = mount(WatchlistSidebar, {
      props: {
        items: [
          { id: 1, symbol: '688256.SH', market: 'cn', display_name: '寒武纪', is_active: true, position_size: 100, average_cost: 1100 },
          { id: 2, symbol: 'HK2513', market: 'hk', display_name: '智谱', is_active: true, position_size: null, average_cost: null },
          { id: 3, symbol: '002384.SZ', market: 'cn', display_name: '东山精密', is_active: true, position_size: 0, average_cost: 199 },
        ],
        quotes: [
          buildQuote(),
          buildQuote({ symbol: 'HK2513', market: 'hk', display_name: '智谱', change_percent: 1 }),
          buildQuote({ symbol: '002384.SZ', display_name: '东山精密', change_percent: 2 }),
        ],
        selectedSymbol: null,
        sparklines: {},
        deleteError: null,
        deleteLoadingSymbol: null,
      },
    });

    expect(wrapper.get('[data-role="stock-card-688256.SH"]').attributes('data-holding')).toBe('true');
    expect(wrapper.get('[data-role="stock-card-HK2513"]').attributes('data-holding')).toBe('false');
    expect(wrapper.get('[data-role="stock-card-002384.SZ"]').attributes('data-holding')).toBe('false');
  });
});
