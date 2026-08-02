import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import ChatMessageList from './ChatMessageList.vue';

describe('ChatMessageList', () => {
  it('shows model reasoning in a dedicated collapsible panel', () => {
    const wrapper = mount(ChatMessageList, {
      props: {
        newsDetail: null,
        messages: [{
          role: 'assistant',
          reasoning: '先核对新闻来源，再比较产业链影响。',
          content: '最终结论。',
          isStreaming: true,
        }],
      },
    });

    const panel = wrapper.get('[data-testid="reasoning-panel"]');
    expect(panel.attributes('open')).toBeDefined();
    expect(panel.text()).toContain('推理中');
    expect(panel.text()).toContain('先核对新闻来源，再比较产业链影响。');
    expect(wrapper.text()).toContain('最终结论。');
  });

  it('does not render a reasoning panel when the provider only returns answer text', () => {
    const wrapper = mount(ChatMessageList, {
      props: {
        newsDetail: null,
        messages: [{ role: 'assistant', content: '普通回答。' }],
      },
    });

    expect(wrapper.find('[data-testid="reasoning-panel"]').exists()).toBe(false);
  });

  it('contains long conversations inside the dedicated message viewport', () => {
    const wrapper = mount(ChatMessageList, {
      props: {
        newsDetail: null,
        messages: [{ role: 'assistant', content: '长回答'.repeat(1000) }],
      },
    });

    expect(wrapper.classes()).toContain('overflow-hidden');
    const viewport = wrapper.get('[data-role="chat-message-viewport"]');
    expect(viewport.classes()).toEqual(expect.arrayContaining(['overflow-y-auto', 'overscroll-contain']));
  });
});
