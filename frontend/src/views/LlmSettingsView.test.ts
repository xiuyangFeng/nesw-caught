import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LlmSettingsView from './LlmSettingsView.vue';

const llmStore = reactive({
  config: null as any,
  configs: [] as any[],
  loading: false,
  saving: false,
  testingConnection: false,
  loadError: null as string | null,
  saveError: null as string | null,
  saveSuccess: null as string | null,
  testError: null as string | null,
  testSuccess: null as string | null,
  loadConfig: vi.fn(),
  loadAllConfigs: vi.fn(),
  saveConfig: vi.fn(),
  testConnection: vi.fn(),
  deleteConfig: vi.fn(),
  setDefaultConfig: vi.fn(),
  toggleConfigActive: vi.fn(),
});

vi.mock('../stores/llmStore', () => ({
  useLlmStore: () => llmStore,
}));

describe('LlmSettingsView', () => {
  beforeEach(() => {
    llmStore.loading = false;
    llmStore.saving = false;
    llmStore.testingConnection = false;
    llmStore.loadError = null;
    llmStore.saveError = null;
    llmStore.saveSuccess = null;
    llmStore.testError = null;
    llmStore.testSuccess = null;
    llmStore.configs = [];
    llmStore.loadConfig.mockReset();
    llmStore.loadAllConfigs.mockReset();
    llmStore.saveConfig.mockReset();
    llmStore.testConnection.mockReset();
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

    expect(wrapper.find('[data-role="llm-settings-grid"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('尚未配置任何模型');
    expect(wrapper.find('input[type="password"]').attributes('placeholder')).toContain('必填 API Key');
    expect(wrapper.find('[data-surface="terminal-field"]').exists()).toBe(true);
  });

  it('shows a load error when llm config cannot be fetched', () => {
    llmStore.loadError = 'backend offline';

    const wrapper = mount(LlmSettingsView);

    expect(wrapper.text()).toContain('backend offline');
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
    await inputs[4].setValue('sk-test-key');
    await wrapper.find('form').trigger('submit.prevent');

    expect(llmStore.saveConfig).toHaveBeenCalledWith({
      id: null,
      provider_name: 'openai_compatible',
      display_name: 'DeepSeek',
      base_url: 'https://example-llm.test/v2',
      model_name: 'deepseek-reasoner',
      api_key: 'sk-test-key',
      is_active: true,
      is_default: false,
    });
    expect(wrapper.text()).toContain('LLM 配置已保存');
  });

  it('renders a saved-config connection test button and calls the store action', async () => {
    llmStore.config = {
      configured: true,
      provider_name: 'openai_compatible',
      display_name: 'DeepSeek',
      model_name: 'deepseek-chat',
      base_url: 'https://api.deepseek.com/v1',
      api_key_set: true,
      updated_at: '2026-03-17T09:00:00Z',
    };
    llmStore.testConnection.mockImplementation(async () => {
      llmStore.testSuccess = '连接成功';
    });

    const wrapper = mount(LlmSettingsView);

    const button = wrapper.find('[data-testid="test-connection-button"]');
    expect(button.exists()).toBe(true);
    await button.trigger('click');

    expect(llmStore.testConnection).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain('连接成功');
  });
});
