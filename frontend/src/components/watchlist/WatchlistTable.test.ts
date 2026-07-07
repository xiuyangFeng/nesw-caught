import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import WatchlistTable from './WatchlistTable.vue';

describe('WatchlistTable', () => {
  it('renders the watchlist table inside a terminal surface shell', () => {
    const wrapper = mount(WatchlistTable, {
      props: {
        selectedSymbol: null,
        rows: [
          {
            symbol: '0700.HK',
            market: 'hk',
            display_name: 'Tencent',
            provider_symbol: '0700.HK',
            price: 546.5,
            change_amount: -3.5,
            change_percent: -0.64,
            source: 'yahoo',
            message: null,
            open_price: 546.5,
            previous_close: 550,
            day_high: 550.5,
            day_low: 542.5,
            volume: 9088272,
            status: 'ok',
            has_hot_alert: false,
            fetched_at: '2026-03-18T04:00:00Z',
          },
        ],
      },
    });

    expect(wrapper.find('[data-surface="terminal-table"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="watchlist-table-shell"]').exists()).toBe(true);
  });

  it('emits delete without triggering row selection', async () => {
    const wrapper = mount(WatchlistTable, {
      props: {
        selectedSymbol: null,
        rows: [
          {
            symbol: '0700.HK',
            market: 'hk',
            display_name: 'Tencent',
            provider_symbol: '0700.HK',
            price: 546.5,
            change_amount: -3.5,
            change_percent: -0.64,
            source: 'yahoo',
            message: null,
            open_price: 546.5,
            previous_close: 550,
            day_high: 550.5,
            day_low: 542.5,
            volume: 9088272,
            status: 'ok',
            has_hot_alert: false,
            fetched_at: '2026-03-18T04:00:00Z',
          },
        ],
      },
    });

    await wrapper.get('button[data-role="delete-watchlist"]').trigger('click');

    expect(wrapper.emitted('delete')).toEqual([['0700.HK']]);
    expect(wrapper.emitted('select')).toBeUndefined();
  });
});
