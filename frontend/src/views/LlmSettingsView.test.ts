import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LlmSettingsView from './LlmSettingsView.vue';

const llmStore = reactive({
  config: null as any,
  loading: false,
  saving: false,
  saveError: null as string | null,
  saveSuccess: null as string | null,
  loadConfig: vi.fn(),
  saveConfig: vi.fn(),
});

vi.mock('../stores/llmStore', () => ({
  useLlmStore: () => llmStore,
}));

describe('LlmSettingsView', () => {
  beforeEach(() => {
    llmStore.loading = false;
    llmStore.saving = false;
    llmStore.saveError = null;
    llmStore.saveSuccess = null;
    llmStore.loadConfig.mockReset();
    llmStore.saveConfig.mockReset();
    llmStore.config = null;
  });

  it('shows an empty-state message when llm is not configured', () => {
    llmStore.config = {
      configured: false,
      provider_name: null,
      display_name: null,
      model_name: null,
      base_url: null,
      api_key_set: false,
      updated_at: null,
    };

    const wrapper = mount(LlmSettingsView);

    expect(wrapper.text()).toContain('尚未配置任何 LLM');
    expect(wrapper.find('input[type="password"]').attributes('placeholder')).toContain('留空表示保留当前 key');
    expect(wrapper.find('[data-surface="terminal-field"]').exists()).toBe(true);
  });

  it('fills existing config and saves updated values', async () => {
    llmStore.config = {
      configured: true,
      provider_name: 'openai_compatible',
      display_name: 'OpenAI Compatible',
      model_name: 'deepseek-chat',
      base_url: 'https://example-llm.test/v1',
      api_key_set: true,
      updated_at: '2026-03-17T09:00:00Z',
    };
    llmStore.saveConfig.mockImplementation(async (payload) => {
      llmStore.config = {
        configured: true,
        provider_name: payload.provider_name,
        display_name: payload.display_name ?? null,
        model_name: payload.model_name,
        base_url: payload.base_url ?? null,
        api_key_set: true,
        updated_at: '2026-03-17T09:10:00Z',
      };
      llmStore.saveSuccess = 'LLM 配置已保存';
    });

    const wrapper = mount(LlmSettingsView);

    const inputs = wrapper.findAll('input');
    await inputs[0].setValue('openai_compatible');
    await inputs[1].setValue('DeepSeek');
    await inputs[2].setValue('https://example-llm.test/v2');
    await inputs[3].setValue('deepseek-reasoner');
    await wrapper.find('form').trigger('submit.prevent');

    expect(llmStore.saveConfig).toHaveBeenCalledWith({
      provider_name: 'openai_compatible',
      display_name: 'DeepSeek',
      base_url: 'https://example-llm.test/v2',
      model_name: 'deepseek-reasoner',
      api_key: undefined,
    });
    expect(wrapper.text()).toContain('LLM 配置已保存');
  });
});
