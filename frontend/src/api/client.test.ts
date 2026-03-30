import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './client';
import { HttpError } from './http';
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

describe('apiClient llm config requests', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('does not fall back to mock llm config when loading config fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(apiClient.getLlmConfig()).rejects.toThrow('backend offline');
  });

  it('does not fall back to mock llm config when saving config fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(
      apiClient.saveLlmConfig({
        provider_name: 'openai_compatible',
        display_name: 'DeepSeek',
        base_url: 'https://api.deepseek.com/v1',
        model_name: 'deepseek-chat',
      }),
    ).rejects.toThrow('backend offline');
  });

  it('posts llm connection tests to the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          provider_name: 'openai_compatible',
          model_name: 'deepseek-chat',
          message: 'LLM connection succeeded',
        }),
      }),
    );

    const response = await apiClient.testLlmConnection();

    expect(fetch).toHaveBeenCalledWith('/api/llm/test', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    expect(response.degraded).toBe(false);
    expect(response.data.message).toBe('LLM connection succeeded');
  });
});

describe('apiClient.getStockKline', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('preserves backend http errors instead of fabricating mock candles', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'watchlist symbol not found' }),
      }),
    );

    const request = apiClient.getStockKline('MISSING', '1d', '6mo');

    await expect(request).rejects.toBeInstanceOf(HttpError);
    await expect(request).rejects.toMatchObject({
      status: 404,
      message: 'watchlist symbol not found',
    });
  });
});

describe('apiClient.getWatchlistCandidates', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('falls back to mock candidates that include a-shares when backend is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    const response = await apiClient.getWatchlistCandidates();

    expect(response.degraded).toBe(true);
    expect(response.data.some((item) => item.symbol === '600519.SH' && item.market === 'cn')).toBe(true);
  });
});

describe('apiClient.getWatchlistResearchBrief', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads the watchlist research brief from the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          symbol: 'NVDA',
          market: 'us',
          generated_at: '2026-03-30T11:30:00Z',
          window_days: 14,
          top_action_level: 'act_now',
          has_unexplained_price_move: false,
          drivers: [],
        }),
      }),
    );

    const response = await apiClient.getWatchlistResearchBrief('NVDA');

    expect(fetch).toHaveBeenCalledWith('/api/watchlist/NVDA/research-brief', {
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
    });
    expect(response.degraded).toBe(false);
    expect(response.data.symbol).toBe('NVDA');
    expect(response.data.window_days).toBe(14);
    expect(response.data.market).toBe('us');
  });

  it('preserves backend failures instead of fabricating an empty brief', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(apiClient.getWatchlistResearchBrief('NVDA')).rejects.toThrow('backend offline');
  });
});

describe('apiClient.getNewsRuntime', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads news runtime from the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          feed_status: 'live',
          last_refresh_finished_at: '2026-03-25T02:40:00Z',
          last_news_created_at: '2026-03-25T02:39:40Z',
          last_incremental_event_at: '2026-03-25T02:39:55Z',
          degraded_market_count: 0,
          markets: [
            {
              market: 'us',
              status: 'live',
              mode: 'primary',
              last_primary_success_at: '2026-03-25T02:39:30Z',
              last_news_created_at: '2026-03-25T02:39:40Z',
              degraded_reason: null,
            },
          ],
          sources: [
            {
              source_name: 'Example Source',
              market: 'us',
              tier: 'primary',
              status: 'ok',
              last_attempt_at: '2026-03-25T02:39:20Z',
              last_success_at: '2026-03-25T02:39:30Z',
              consecutive_failures: 0,
              avg_fetch_latency_ms: 320,
              latest_news_published_at: '2026-03-25T02:35:00Z',
              latest_news_fetched_at: '2026-03-25T02:39:30Z',
              last_error: null,
            },
          ],
        }),
      }),
    );

    const response = await apiClient.getNewsRuntime();

    expect(fetch).toHaveBeenCalledWith('/api/news/runtime', {
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
    });
    expect(response.degraded).toBe(false);
    expect(response.data.feed_status).toBe('live');
    expect(response.data.sources).toHaveLength(1);
  });
});

describe('apiClient.getNewsEventDetail', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads event detail from the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          event_key: 'topic-1',
          event_title: 'AI Chip Launch',
          event_summary: 'Summary',
          event_type: 'product',
          market: 'us',
          sentiment_label: 'positive',
          importance_score: 0.91,
          last_seen_at: '2026-03-30T00:00:00Z',
          primary_symbol: 'NVDA',
          related_symbols: ['NVDA', 'SMCI'],
          source_count: 2,
          news_count: 2,
          news_items: [],
        }),
      }),
    );

    const response = await apiClient.getNewsEventDetail('topic-1');

    expect(fetch).toHaveBeenCalledWith('/api/news/events/topic-1', {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });
    expect(response.degraded).toBe(false);
    expect(response.data.event_key).toBe('topic-1');
  });

  it('preserves backend 404 errors for the caller', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'event not found' }),
      }),
    );

    await expect(apiClient.getNewsEventDetail('topic-504')).rejects.toMatchObject({
      message: 'event not found',
      status: 404,
    });
  });

  it('preserves backend 500 errors for the caller', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'event detail rebuild failed' }),
      }),
    );

    await expect(apiClient.getNewsEventDetail('topic-504')).rejects.toMatchObject({
      message: 'event detail rebuild failed',
      status: 500,
    });
  });

  it('surfaces network failures instead of falling back to mock data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network offline')));

    await expect(apiClient.getNewsEventDetail('topic-1')).rejects.toMatchObject({
      message: 'network offline',
    });
  });
});
