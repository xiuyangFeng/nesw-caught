import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { CalendarResponse } from '../types/api';
import CalendarView from './CalendarView.vue';

const mockPush = vi.fn();

const { getCalendar } = vi.hoisted(() => ({
  getCalendar: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock('../api/client', () => ({
  apiClient: {
    getCalendar,
  },
}));

const response: CalendarResponse = {
  days: 30,
  events: [
    { symbol: 'AAPL', display_name: 'Apple', event_type: 'earnings', date: '2026-07-15', days_until: 1 },
    { symbol: 'TSLA', display_name: 'Tesla', event_type: 'ex_dividend', date: '2026-07-20', days_until: 6 },
  ],
  summaries: [],
  skipped_count: 1,
  generated_at: '2026-07-14T00:00:00Z',
};

describe('CalendarView', () => {
  beforeEach(() => {
    mockPush.mockReset();
    getCalendar.mockReset();
    getCalendar.mockResolvedValue({ data: response, degraded: false });
  });

  it('loads and renders grouped calendar events with the overview counters', async () => {
    const wrapper = mount(CalendarView);
    await flushPromises();

    expect(getCalendar).toHaveBeenCalledWith(30);
    expect(wrapper.text()).toContain('财报 1');
    expect(wrapper.text()).toContain('除息 1');
    expect(wrapper.text()).toContain('跳过 1');
    expect(wrapper.text()).toContain('Apple');
    expect(wrapper.text()).toContain('Tesla');
    expect(wrapper.find('[data-role="calendar-group-2026-07-15"]').exists()).toBe(true);
  });

  it('shows the empty state when there are no upcoming events', async () => {
    getCalendar.mockResolvedValue({
      data: { days: 30, events: [], summaries: [], skipped_count: 0, generated_at: '2026-07-14T00:00:00Z' },
      degraded: false,
    });

    const wrapper = mount(CalendarView);
    await flushPromises();

    expect(wrapper.text()).toContain('未来窗口内暂无财报 / 除息事件');
    expect(wrapper.text()).not.toContain('跳过');
  });

  it('shows an error message and falls back to the empty state when the calendar API fails', async () => {
    getCalendar.mockRejectedValue(new Error('日历服务异常'));

    const wrapper = mount(CalendarView);
    await flushPromises();

    expect(wrapper.text()).toContain('日历服务异常');
    expect(wrapper.text()).toContain('未来窗口内暂无财报 / 除息事件');
  });

  it('reloads the calendar with a new window when a window option is clicked', async () => {
    const wrapper = mount(CalendarView);
    await flushPromises();
    getCalendar.mockClear();

    const buttons = wrapper.findAll('[data-role="calendar-window-switch"] button');
    expect(buttons.map((b) => b.text())).toEqual(['未来 14 天', '未来 30 天', '未来 60 天', '未来 90 天']);

    await buttons[2].trigger('click');
    await flushPromises();

    expect(getCalendar).toHaveBeenCalledWith(60);
    expect(wrapper.text()).toContain('未来 60 天');
  });

  it('routes to the symbol watchlist detail page when an event row is clicked', async () => {
    const wrapper = mount(CalendarView);
    await flushPromises();

    await wrapper.get('[data-role="calendar-event-AAPL"]').trigger('click');

    expect(mockPush).toHaveBeenCalledWith({ name: 'watchlist-detail', params: { symbol: 'AAPL' } });
  });
});
