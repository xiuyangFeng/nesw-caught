import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './client';
import { HttpError } from './http';
import { mockLlmConfig, mockLlmStats, mockMarketOverview } from './mock';

describe('apiClient write operations', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('rejects saveFeishuConfig when the backend is unavailable instead of faking success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(
      apiClient.saveFeishuConfig({
        app_id: 'cli_test123',
        target_type: 'chat',
        target_id: 'oc_test_chat_id',
        news_enabled: true,
        news_keywords: null,
        news_batch_interval_minutes: 30,
        alert_enabled: true,
        analysis_enabled: true,
        is_active: true,
      }),
    ).rejects.toThrow('backend offline');
  });

  it('rejects delete operations with the backend error instead of mutating mock data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'internal error' }),
      }),
    );

    await expect(apiClient.deleteLlmConfig(1)).rejects.toMatchObject({ status: 500, message: 'internal error' });
    await expect(apiClient.deleteWatchlist('NVDA')).rejects.toMatchObject({ status: 500, message: 'internal error' });
    await expect(apiClient.deleteXAccount('elonmusk')).rejects.toMatchObject({ status: 500, message: 'internal error' });
  });

  it('rejects account and config mutations when the backend is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(apiClient.setDefaultLlmConfig(1)).rejects.toThrow('backend offline');
    await expect(apiClient.toggleLlmConfigActive(1, false)).rejects.toThrow('backend offline');
    await expect(
      apiClient.createXAccount({
        handle: 'tester',
        display_name: 'Tester',
        market_focus: 'us',
        is_active: true,
        priority: 0,
        tier: 'watch',
        notes: null,
      }),
    ).rejects.toThrow('backend offline');
    await expect(apiClient.updateXAccount('tester', { is_active: false })).rejects.toThrow('backend offline');
    await expect(apiClient.refreshNews()).rejects.toThrow('backend offline');
    await expect(apiClient.analyzeNews(1)).rejects.toThrow('backend offline');
  });

  it('requests an async-mode refresh so the scrape runs as a background task', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({ status: 'accepted', message: 'News refresh started in background' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiClient.refreshNews();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/news/refresh?async_mode=true',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});

describe('apiClient read fallbacks in production builds', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('propagates read failures instead of serving mock data when not in dev', async () => {
    vi.stubEnv('DEV', false);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(apiClient.getWatchlistCandidates()).rejects.toThrow('backend offline');
    await expect(apiClient.getNews()).rejects.toThrow('backend offline');
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
        is_active: true,
        is_default: false,
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

describe('apiClient.getNewsEventDetail', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('accepts watchlist hits in the event detail payload', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          event_key: 'ai-chip-launch',
          event_title: 'AI Chip Launch',
          event_summary: 'NVIDIA 新一轮 AI 芯片发布带动供应链关注度上升。',
          event_type: 'product',
          market: 'us',
          sentiment_label: 'positive',
          importance_score: 0.93,
          last_seen_at: '2026-03-18T08:00:00Z',
          primary_symbol: 'NVDA',
          related_symbols: ['NVDA', 'SMCI'],
          watchlist_hits: ['NVIDIA', 'Supermicro'],
          source_count: 2,
          news_count: 2,
          news_items: [],
        }),
      }),
    );

    const response = await apiClient.getNewsEventDetail('ai-chip-launch');

    expect(response.degraded).toBe(false);
    expect(response.data.watchlist_hits).toEqual(['NVIDIA', 'Supermicro']);
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
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
    });
    expect(response.degraded).toBe(false);
    expect(response.data.event_key).toBe('topic-1');
  });

  it('falls back to mock event detail when the backend 404s, like other read endpoints', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: 'event not found' }),
      }),
    );

    const response = await apiClient.getNewsEventDetail('topic-504');

    expect(response.degraded).toBe(true);
    expect(response.data.event_key).toBe('topic-504');
  });

  it('falls back to mock event detail when the backend 500s, like other read endpoints', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: 'event detail rebuild failed' }),
      }),
    );

    const response = await apiClient.getNewsEventDetail('topic-504');

    expect(response.degraded).toBe(true);
    expect(response.data.event_key).toBe('topic-504');
  });

  it('falls back to mock event detail on network failures in dev builds', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network offline')));

    const response = await apiClient.getNewsEventDetail('topic-1');

    expect(response.degraded).toBe(true);
    expect(response.data.event_key).toBeTruthy();
  });

  it('propagates event detail failures instead of serving mock data when not in dev', async () => {
    vi.stubEnv('DEV', false);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(apiClient.getNewsEventDetail('topic-1')).rejects.toThrow('backend offline');

    vi.unstubAllEnvs();
  });
});

describe('apiClient.pingLlmConfig', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts ping configuration requests to the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          provider_name: 'openai_compatible',
          model_name: 'deepseek-chat',
          message: 'LLM connection succeeded',
          latency_ms: 120,
        }),
      }),
    );

    const response = await apiClient.pingLlmConfig(1);

    expect(fetch).toHaveBeenCalledWith('/api/llm/config/1/ping', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    expect(response.degraded).toBe(false);
    expect(response.data.latency_ms).toBe(120);
  });
});

describe('apiClient.getWatchlistAiInsight', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads the watchlist stock ai insight from the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          symbol: '0700.HK',
          insight_text: '# AI Insight\nPositive outlook.',
          generated_at: '2026-06-12T15:20:00Z',
        }),
      }),
    );

    const response = await apiClient.getWatchlistAiInsight('0700.HK');

    expect(fetch).toHaveBeenCalledWith('/api/watchlist/0700.HK/ai-insight', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    expect(response.degraded).toBe(false);
    expect(response.data.insight_text).toBe('# AI Insight\nPositive outlook.');
  });

  it('falls back to a generated placeholder insight for symbols without curated mock data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    const response = await apiClient.getWatchlistAiInsight('ZZZZ.US');

    expect(response.degraded).toBe(true);
    expect(response.data.symbol).toBe('ZZZZ.US');
    expect(response.data.insight_text).toContain('ZZZZ.US');
  });
});

describe('apiClient.getLlmStats', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('falls back to the shared mock llm stats fixture when the backend is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    const response = await apiClient.getLlmStats();

    expect(response.degraded).toBe(true);
    expect(response.data).toEqual(mockLlmStats);
  });

  it('propagates read failures instead of serving mock stats when not in dev', async () => {
    vi.stubEnv('DEV', false);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(apiClient.getLlmStats()).rejects.toThrow('backend offline');
  });
});

describe('apiClient market overview endpoints', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('loads the market overview aggregate from the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ generated_at: '2026-08-02T08:00:00Z', markets: [] }),
      }),
    );

    const response = await apiClient.getMarketOverview();

    expect(fetch).toHaveBeenCalledWith('/api/market/overview', {
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
    });
    expect(response.degraded).toBe(false);
    expect(response.data.generated_at).toBe('2026-08-02T08:00:00Z');
  });

  it('falls back to the bundled five-market mock overview when the backend is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    const response = await apiClient.getMarketOverview();

    expect(response.degraded).toBe(true);
    expect(response.data).toEqual(mockMarketOverview);
    expect(response.data.markets.map((market) => market.market)).toEqual(['us', 'cn', 'kr', 'jp', 'eu']);
  });

  it('propagates overview read failures instead of serving mock data when not in dev', async () => {
    vi.stubEnv('DEV', false);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(apiClient.getMarketOverview()).rejects.toThrow('backend offline');
  });

  it('loads the index config list from the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          { id: 1, symbol: '^GSPC', market: 'us', display_name: '标普500', kind: 'index', sort_order: 0, enabled: true },
        ],
      }),
    );

    const response = await apiClient.getMarketIndexConfig();

    expect(fetch).toHaveBeenCalledWith('/api/market/index-config', {
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
    });
    expect(response.degraded).toBe(false);
    expect(response.data).toHaveLength(1);
  });

  it('posts new index config entries to the backend', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: 9, symbol: '^NDX', market: 'us', display_name: '纳指100', kind: 'index', sort_order: 3, enabled: true }),
      }),
    );

    const payload = { symbol: '^NDX', market: 'us' as const, display_name: '纳指100', kind: 'index' as const };
    const response = await apiClient.createMarketIndexConfig(payload);

    expect(fetch).toHaveBeenCalledWith('/api/market/index-config', {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    expect(response.degraded).toBe(false);
    expect(response.data.id).toBe(9);
  });

  it('patches index config entries without sending symbol or market', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ id: 1, symbol: '^GSPC', market: 'us', display_name: '标普500指数', kind: 'index', sort_order: 1, enabled: false }),
      }),
    );

    const payload = { display_name: '标普500指数', sort_order: 1, enabled: false };
    const response = await apiClient.updateMarketIndexConfig(1, payload);

    expect(fetch).toHaveBeenCalledWith('/api/market/index-config/1', {
      method: 'PATCH',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    expect(response.degraded).toBe(false);
    expect(response.data.enabled).toBe(false);
  });

  it('deletes index config entries via the contract endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 204, json: async () => null }));

    await apiClient.deleteMarketIndexConfig(1);

    expect(fetch).toHaveBeenCalledWith('/api/market/index-config/1', {
      method: 'DELETE',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
    });
  });

  it('rejects index config mutations when the backend is unavailable instead of faking success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('backend offline')));

    await expect(
      apiClient.createMarketIndexConfig({ symbol: '^NDX', market: 'us', display_name: '纳指100' }),
    ).rejects.toThrow('backend offline');
    await expect(apiClient.updateMarketIndexConfig(1, { enabled: false })).rejects.toThrow('backend offline');
    await expect(apiClient.deleteMarketIndexConfig(1)).rejects.toThrow('backend offline');
  });
});
