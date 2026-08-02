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
  pingStatuses: {} as Record<number, { loading: boolean; latency: number | null; error: string | null }>,
  loadConfig: vi.fn(),
  loadAllConfigs: vi.fn(),
  saveConfig: vi.fn(),
  testConnection: vi.fn(),
  deleteConfig: vi.fn(),
  setDefaultConfig: vi.fn(),
  toggleConfigActive: vi.fn(),
  pingConfig: vi.fn(),
});

vi.mock('../stores/llmStore', () => ({
  useLlmStore: () => llmStore,
}));

const toastStore = {
  show: vi.fn(),
  showSuccess: vi.fn(),
  showError: vi.fn(),
  showWarning: vi.fn(),
  showInfo: vi.fn(),
  remove: vi.fn(),
};

vi.mock('../stores/toastStore', () => ({
  useToastStore: () => toastStore,
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
    llmStore.pingStatuses = {};
    llmStore.configs = [];
    llmStore.loadConfig.mockReset();
    llmStore.loadAllConfigs.mockReset();
    llmStore.saveConfig.mockReset();
    llmStore.testConnection.mockReset();
    llmStore.pingConfig.mockReset();
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

    // Select by name attribute rather than positional index so the assertion
    // stays stable as the config form grows new fields (e.g. pricing/budget).
    await wrapper.find('input[name="provider_name"]').setValue('openai_compatible');
    await wrapper.find('input[name="display_name"]').setValue('DeepSeek');
    await wrapper.find('input[name="base_url"]').setValue('https://example-llm.test/v2');
    await wrapper.find('input[name="model_name"]').setValue('deepseek-reasoner');
    await wrapper.find('input[name="api_key"]').setValue('sk-test-key');
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
      input_price_per_1k: null,
      output_price_per_1k: null,
      monthly_budget_usd: null,
    });
    expect(wrapper.text()).toContain('LLM 配置已保存');
  });

  it('submits numeric pricing fields without crashing the settings module', async () => {
    const wrapper = mount(LlmSettingsView);

    await wrapper.find('input[name="provider_name"]').setValue('openai_compatible');
    await wrapper.find('input[name="base_url"]').setValue('https://api.deepseek.com/v1');
    await wrapper.find('input[name="model_name"]').setValue('deepseek-chat');
    await wrapper.find('input[name="api_key"]').setValue('sk-test-key');
    await wrapper.find('input[name="input_price_per_1k"]').setValue('0.0002');
    await wrapper.find('input[name="output_price_per_1k"]').setValue('0.002');
    await wrapper.find('input[name="monthly_budget_usd"]').setValue('25');
    await wrapper.find('form').trigger('submit.prevent');

    expect(llmStore.saveConfig).toHaveBeenCalledWith(expect.objectContaining({
      input_price_per_1k: 0.0002,
      output_price_per_1k: 0.002,
      monthly_budget_usd: 25,
    }));
    expect(wrapper.text()).not.toContain('raw.trim is not a function');
  });

  it('shows inline validation and blocks malformed URLs and negative pricing', async () => {
    const wrapper = mount(LlmSettingsView);

    await wrapper.find('input[name="provider_name"]').setValue('openai_compatible');
    await wrapper.find('input[name="base_url"]').setValue('deepseek-api');
    await wrapper.find('input[name="model_name"]').setValue('deepseek-chat');
    await wrapper.find('input[name="api_key"]').setValue('sk-test-key');
    await wrapper.find('input[name="input_price_per_1k"]').setValue('-0.1');

    expect(wrapper.text()).toContain('请输入完整有效的 Base URL');
    expect(wrapper.text()).toContain('输入单价不能小于 0');
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined();
    expect(llmStore.saveConfig).not.toHaveBeenCalled();
  });

  it('requires a new API key only when an edited config changes its Base URL', async () => {
    llmStore.configs = [{
      configured: true,
      id: 7,
      provider_name: 'openai_compatible',
      display_name: 'DeepSeek',
      base_url: 'https://api.deepseek.com/v1',
      model_name: 'deepseek-chat',
      api_key_set: true,
      is_active: true,
      is_default: true,
      input_price_per_1k: 0.0002,
      output_price_per_1k: 0.002,
      monthly_budget_usd: 25,
      updated_at: '2026-08-02T08:00:00Z',
    }];

    const wrapper = mount(LlmSettingsView);
    const editButton = wrapper.findAll('button').find(button => button.text() === '编辑');
    expect(editButton).toBeDefined();
    await editButton!.trigger('click');

    await wrapper.find('form').trigger('submit.prevent');
    expect(llmStore.saveConfig).toHaveBeenCalledWith(expect.objectContaining({
      id: 7,
      api_key: undefined,
      base_url: 'https://api.deepseek.com/v1',
    }));

    llmStore.saveConfig.mockClear();
    await editButton!.trigger('click');
    await wrapper.find('input[name="base_url"]').setValue('https://gateway.example.com/v1');
    expect(wrapper.text()).toContain('修改 Base URL 后必须重新输入明文 API Key');
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined();

    await wrapper.find('input[name="api_key"]').setValue('sk-replacement-key');
    await wrapper.find('form').trigger('submit.prevent');
    expect(llmStore.saveConfig).toHaveBeenCalledWith(expect.objectContaining({
      id: 7,
      api_key: 'sk-replacement-key',
      base_url: 'https://gateway.example.com/v1',
    }));
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
