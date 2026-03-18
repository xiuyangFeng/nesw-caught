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
            price: 546.5,
            change_percent: -0.64,
            open_price: 546.5,
            previous_close: 550,
            day_high: 550.5,
            day_low: 542.5,
            volume: 9088272,
            is_abnormal: false,
            abnormal_reason: null,
            status: 'ok',
            fetched_at: '2026-03-18T04:00:00Z',
          },
        ],
      },
    });

    expect(wrapper.find('[data-surface="terminal-table"]').exists()).toBe(true);
  });
});
