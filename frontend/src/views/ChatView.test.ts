import { flushPromises, mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { LLMConfigSummary } from '../types/api';
import ChatView from './ChatView.vue';

const mockPush = vi.fn();
const mockReplace = vi.fn();
const routeState = reactive<{ query: Record<string, unknown> }>({ query: {} });

const { getNewsDetail } = vi.hoisted(() => ({
  getNewsDetail: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

vi.mock('../api/client', () => ({
  apiClient: {
    getNewsDetail,
  },
}));

const toastStore = {
  showSuccess: vi.fn(),
  showError: vi.fn(),
  showWarning: vi.fn(),
  showInfo: vi.fn(),
};

vi.mock('../stores/toastStore', () => ({
  useToastStore: () => toastStore,
}));

const activeConfigs: LLMConfigSummary[] = [
  {
    id: 1,
    configured: true,
    provider_name: 'openai_compatible',
    display_name: 'DeepSeek',
    model_name: 'deepseek-chat',
    base_url: null,
    api_key_set: true,
    is_active: true,
    is_default: true,
    updated_at: null,
  },
  {
    id: 2,
    configured: true,
    provider_name: 'openai_compatible',
    display_name: 'GPT-4o',
    model_name: 'gpt-4o',
    base_url: null,
    api_key_set: true,
    is_active: true,
    is_default: false,
    updated_at: null,
  },
];

const llmStore = reactive({
  configs: [] as LLMConfigSummary[],
  loadAllConfigs: vi.fn(async () => undefined),
});

vi.mock('../stores/llmStore', () => ({
  useLlmStore: () => llmStore,
}));

function sseResponse(chunks: string[]) {
  let index = 0;
  return {
    ok: true,
    body: {
      getReader: () => ({
        read: async () => {
          if (index < chunks.length) {
            return { done: false, value: new TextEncoder().encode(chunks[index++]) };
          }
          return { done: true, value: undefined };
        },
      }),
    },
  };
}

describe('ChatView', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    mockPush.mockReset();
    mockReplace.mockReset();
    getNewsDetail.mockReset();
    getNewsDetail.mockResolvedValue({ data: null, degraded: false });
    toastStore.showSuccess.mockClear();
    toastStore.showError.mockClear();
    toastStore.showWarning.mockClear();
    toastStore.showInfo.mockClear();
    llmStore.configs = [...activeConfigs];
    llmStore.loadAllConfigs.mockClear();
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('renders the default session greeting and the active model picker', async () => {
    const wrapper = mount(ChatView);
    await flushPromises();

    expect(llmStore.loadAllConfigs).toHaveBeenCalled();
    expect(wrapper.text()).toContain('AI 对话助手');
    expect(wrapper.text()).toContain('你好！我是 AI 智能助理');

    const options = wrapper.findAll('select option');
    expect(options.map((o) => o.text())).toEqual(['DeepSeek (deepseek-chat)', 'GPT-4o (gpt-4o)']);
    expect((wrapper.get('select').element as HTMLSelectElement).value).toBe('1');
  });

  it('keeps the chat workspace constrained to the viewport so only the message pane scrolls', async () => {
    const wrapper = mount(ChatView);
    await flushPromises();

    const workspace = wrapper.get('[data-role="chat-workspace"]');
    expect(workspace.classes()).toEqual(expect.arrayContaining([
      'h-[calc(100dvh-100px)]',
      'min-h-0',
      'overflow-hidden',
    ]));

    const mainColumn = wrapper.get('[data-role="chat-main-column"]');
    expect(mainColumn.classes()).toEqual(expect.arrayContaining(['min-h-0', 'overflow-hidden']));
  });

  it('shows a warning and disables the composer when there are no active LLM configs', async () => {
    llmStore.configs = [];
    const wrapper = mount(ChatView);
    await flushPromises();

    expect(wrapper.text()).toContain('暂无可用模型，请先去配置');
    expect(wrapper.find('select').exists()).toBe(false);
    expect(wrapper.get('input[type="text"]').attributes('disabled')).toBeDefined();
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined();
  });

  it('sends a message and streams the assistant reply into the message list', async () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValue(sseResponse(['data: {"text":"你好，"}\n', 'data: {"text":"世界"}\n\n']));

    const wrapper = mount(ChatView);
    await vi.advanceTimersByTimeAsync(0);

    await wrapper.get('input[type="text"]').setValue('你好 AI');
    await wrapper.get('form').trigger('submit');
    await vi.advanceTimersByTimeAsync(2000);

    expect(fetchMock).toHaveBeenCalledWith('/api/llm/chat', expect.objectContaining({ method: 'POST' }));
    expect(wrapper.text()).toContain('你好 AI');
    expect(wrapper.text()).toContain('你好，世界');
  });

  it('shows a failed-send message in the chat log without crashing on API error', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      json: async () => ({ detail: '模型配置无效' }),
    });

    const wrapper = mount(ChatView);
    await flushPromises();

    await wrapper.get('input[type="text"]').setValue('测试消息');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(wrapper.text()).toContain('【发送失败】');
    expect(wrapper.text()).toContain('模型配置无效');
    expect(toastStore.showError).toHaveBeenCalledWith('模型配置无效');
  });

  it('creates a new chat session from the sidebar', async () => {
    const wrapper = mount(ChatView);
    await flushPromises();

    expect(wrapper.findAll('aside .group')).toHaveLength(1);

    await wrapper.get('aside button').trigger('click');
    await flushPromises();

    expect(wrapper.findAll('aside .group')).toHaveLength(2);
  });
});
