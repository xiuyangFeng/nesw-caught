import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './client';
import { mockFeishuConfig } from './mock';

describe('apiClient.saveFeishuConfig', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    mockFeishuConfig.configured = false;
    mockFeishuConfig.app_id = null;
    mockFeishuConfig.app_secret_set = false;
    mockFeishuConfig.target_type = null;
    mockFeishuConfig.target_id = null;
    mockFeishuConfig.news_enabled = true;
    mockFeishuConfig.news_keywords = null;
    mockFeishuConfig.news_batch_interval_minutes = 60;
    mockFeishuConfig.alert_enabled = true;
    mockFeishuConfig.analysis_enabled = true;
    mockFeishuConfig.is_active = true;
    mockFeishuConfig.updated_at = null;
  });

  it('preserves app_secret_set in mock mode when secret is omitted', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new Error('backend offline')),
    );
    mockFeishuConfig.configured = true;
    mockFeishuConfig.app_secret_set = true;

    const response = await apiClient.saveFeishuConfig({
      app_id: 'cli_test123',
      target_type: 'chat',
      target_id: 'oc_test_chat_id',
      news_enabled: true,
      news_keywords: null,
      news_batch_interval_minutes: 30,
      alert_enabled: true,
      analysis_enabled: true,
      is_active: true,
    });

    expect(response.degraded).toBe(true);
    expect(response.data.app_secret_set).toBe(true);
  });
});
