import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import ResearchBriefPanel from './ResearchBriefPanel.vue';

describe('ResearchBriefPanel', () => {
  it('renders grouped research drivers with the top action level', () => {
    const wrapper = mount(ResearchBriefPanel, {
      props: {
        researchBrief: {
          symbol: 'NVDA',
          market: 'us',
          generated_at: '2026-03-30T11:30:00Z',
          window_days: 14,
          top_action_level: 'act_now',
          has_unexplained_price_move: false,
          drivers: [
            {
              category: 'policy_macro',
              action_level: 'act_now',
              reason: '政策或监管信号直接影响该标的的中期预期。优先级高，建议立即核对原文。',
              news_item: {
                id: 1,
                title: 'US export control policy tightens AI chip shipments',
                summary: 'New policy guidance targets advanced AI accelerators.',
                source_name: 'Reuters',
                canonical_url: null,
                market: 'us',
                sentiment_label: 'neutral',
                published_at: '2026-03-30T10:00:00Z',
                fetched_at: '2026-03-30T10:05:00Z',
              },
            },
          ],
        },
      },
    });

    expect(wrapper.get('[data-role="research-brief-panel"]').text()).toContain('Research Brief');
    expect(wrapper.get('[data-role="research-brief-summary"]').text()).toContain('立即看');
    expect(wrapper.get('[data-role="research-driver-group-policy_macro"]').text()).toContain('政策/监管/宏观');
    expect(wrapper.get('[data-role="research-driver-item-1"]').text()).toContain('Reuters');
  });

  it('renders the empty-state copy when there are no drivers', () => {
    const wrapper = mount(ResearchBriefPanel, {
      props: {
        researchBrief: {
          symbol: 'AAPL',
          market: 'us',
          generated_at: '2026-03-30T11:30:00Z',
          window_days: 14,
          top_action_level: 'none',
          has_unexplained_price_move: false,
          drivers: [],
        },
      },
    });

    expect(wrapper.get('[data-role="research-brief-empty"]').text()).toContain('暂无可归因驱动');
  });

  it('formats the summary timestamp using the brief market timezone', () => {
    const wrapper = mount(ResearchBriefPanel, {
      props: {
        researchBrief: {
          symbol: '600519.SH',
          market: 'cn',
          generated_at: '2026-03-30T00:30:00Z',
          window_days: 14,
          top_action_level: 'none',
          has_unexplained_price_move: false,
          drivers: [],
        },
      },
    });

    expect(wrapper.get('[data-role="research-brief-summary"]').text()).toContain('03/30 08:30');
  });
});
