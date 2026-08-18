import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DeskReportCardView from './DeskReportCardView.vue';

const { getQuantReportCard } = vi.hoisted(() => ({ getQuantReportCard: vi.fn() }));

vi.mock('../api/client', () => ({
  apiClient: { getQuantReportCard },
}));

describe('DeskReportCardView', () => {
  beforeEach(() => {
    getQuantReportCard.mockResolvedValue({
      data: {
        window: '30d',
        sleeves: {
          event_catalyst: { qualified: 0, watch: 1 },
          trend_flow: { qualified: 0, watch: 0 },
          fundamental_revalue: { qualified: 0, watch: 0 },
        },
        sample_size: 1,
        note: '不宣称超额收益',
      },
      degraded: false,
    });
  });

  it('renders sleeve funnel counts without claiming alpha', async () => {
    const wrapper = mount(DeskReportCardView);
    await flushPromises();
    expect(wrapper.find('[data-role="desk-report-card-view"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="desk-report-funnel"]').text()).toContain('事件/催化');
    expect(wrapper.text()).toContain('不宣称超额收益');
  });
});
