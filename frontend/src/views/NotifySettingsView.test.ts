import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import NotifySettingsView from './NotifySettingsView.vue';

const notifyStore = reactive({
  config: null as any,
  loading: false,
  saving: false,
  testing: false,
  saveError: null as string | null,
  saveSuccess: null as string | null,
  testResult: null as { success: boolean; message: string } | null,
  loadConfig: vi.fn(),
  saveConfig: vi.fn(),
  sendTest: vi.fn(),
});

vi.mock('../stores/notifyStore', () => ({
  useNotifyStore: () => notifyStore,
}));

describe('NotifySettingsView', () => {
  beforeEach(() => {
    notifyStore.loading = false;
    notifyStore.saving = false;
    notifyStore.testing = false;
    notifyStore.saveError = null;
    notifyStore.saveSuccess = null;
    notifyStore.testResult = null;
    notifyStore.loadConfig.mockReset();
    notifyStore.saveConfig.mockReset();
    notifyStore.sendTest.mockReset();
    notifyStore.config = {
      configured: true,
      app_id: 'cli_xxx',
      app_secret_set: true,
      target_type: 'chat',
      target_id: 'oc_123',
      news_enabled: true,
      news_keywords: 'AI,半导体',
      news_batch_interval_minutes: 60,
      alert_enabled: true,
      analysis_enabled: true,
      is_active: true,
      updated_at: '2026-03-18T10:00:00Z',
    };
  });

  it('renders notify settings shell and sends a test message', async () => {
    notifyStore.sendTest.mockImplementation(async () => {
      notifyStore.testResult = {
        success: true,
        message: '测试消息已发送',
      };
    });

    const wrapper = mount(NotifySettingsView);

    expect(wrapper.find('[data-role="notify-settings-grid"]').exists()).toBe(true);
    await wrapper.find('[data-role="notify-test-button"]').trigger('click');

    expect(notifyStore.sendTest).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain('测试消息已发送');
  });
});
