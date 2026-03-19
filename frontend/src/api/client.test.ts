import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './client';
import { mockFeishuConfig, mockLlmConfig } from './mock';

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
    mockLlmConfig.configured = true;
    mockLlmConfig.provider_name = 'openai_compatible';
    mockLlmConfig.display_name = 'OpenAI Compatible';
    mockLlmConfig.model_name = 'deepseek-chat';
    mockLlmConfig.base_url = 'https://example-llm.test/v1';
    mockLlmConfig.api_key_set = true;
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

describe('apiClient.translateText', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts translation requests to the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          provider_name: 'openai_compatible',
          model_name: 'deepseek-chat',
          translated_text: '这是翻译结果',
        }),
      }),
    );

    const response = await apiClient.translateText({ text: 'Hello world' });

    expect(fetch).toHaveBeenCalledWith('/api/llm/translate', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text: 'Hello world' }),
    });
    expect(response.degraded).toBe(false);
    expect(response.data.translated_text).toBe('这是翻译结果');
  });

  it('falls back to mock translation when backend is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    const response = await apiClient.translateText({ text: 'Early testers are saying M2.7 is better.' });

    expect(response.degraded).toBe(true);
    expect(response.data.provider_name).toBe(mockLlmConfig.provider_name);
    expect(response.data.translated_text.length).toBeGreaterThan(0);
  });

  it('preserves backend business errors for the caller', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'llm provider is not configured' }),
      }),
    );

    await expect(apiClient.translateText({ text: 'Hello world' })).rejects.toMatchObject({
      message: 'llm provider is not configured',
      status: 400,
    });
  });
});
