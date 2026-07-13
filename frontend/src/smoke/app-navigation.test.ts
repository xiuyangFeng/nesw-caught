import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent, nextTick } from 'vue';
import type { Router } from 'vue-router';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

// ---------------------------------------------------------------------------
// 全应用导航 E2E 冒烟测试 —— 守护「切换模块不崩」这一回归。
//
// 背景：历史上出现过「切换模块卡死必须刷新」的 bug，根因是路由视图缺少错误
// 处理；修复方案是在 <RouterView> 外包一层 <RouteErrorBoundary>（见
// components/common/RouteErrorBoundary.vue）并给懒加载路由加容错恢复。
//
// 本测试用**真实的 vue-router 路由表**（../router）+ **真实的 RouteErrorBoundary**
// 包裹 <RouterView>，逐个访问每一个主模块路由，断言：
//   1. 没有出现 [data-role="route-error-boundary"]（即该视图没有崩进错误边界）；
//   2. 渲染出了该视图的一个可辨识节点（页面标题文本或根 data-role）。
//
// 为保证**离线确定性**：整体 mock 掉 ../api/client 的 apiClient（所有方法返回
// 良性/空数据，不发起真实网络），并 stub 掉重组件依赖（lightweight-charts 图表、
// jsdom 缺失的 IntersectionObserver / ResizeObserver）。不依赖后端、不真联网。
//
// 注意：真实挂载带 Pinia 的应用会触发 Pinia devtools（@vue/devtools-kit），后者在
// 模块求值时读取全局 localStorage；Node 22+ 的实验性全局 storage 未配文件路径会抛
// SecurityError。这一环境问题由 vitest.setup.ts 全局兜底（内存 storage）解决；本文件
// 只需把 ../router 与 RouteErrorBoundary 放到 beforeAll 里与 Shell 定义就近动态 import。
// ---------------------------------------------------------------------------

// 图表库在 jsdom 里没有可用的 canvas，替换成无副作用的空实现，避免噪音/抛错。
vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    addSeries: () => ({ setData: vi.fn(), setMarkers: vi.fn(), applyOptions: vi.fn() }),
    remove: vi.fn(),
    applyOptions: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn(), applyOptions: vi.fn(), subscribeVisibleLogicalRangeChange: vi.fn() }),
    priceScale: () => ({ applyOptions: vi.fn() }),
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
  }),
  LineSeries: Symbol('LineSeries'),
  CandlestickSeries: Symbol('CandlestickSeries'),
  HistogramSeries: Symbol('HistogramSeries'),
}));

// 整体 mock apiClient：复用应用自带的良性 mock 夹具（../api/mock，正是 apiClient
// 在降级模式下会返回的数据，形状天然正确），保证每个页面都能拿到可渲染的数据；
// 未显式覆盖的方法（多为写操作，视图挂载时不会调用）经 Proxy 兜底返回空数据。
vi.mock('../api/client', async () => {
  const mock = await import('../api/mock');
  const ok = <T>(data: T) => Promise.resolve({ data, degraded: false });
  const iso = () => new Date().toISOString();
  const firstOf = <T>(record: Record<string, T>): T | null => {
    const values = Object.values(record);
    return values.length > 0 ? values[0] : null;
  };

  const explicit: Record<string, (...args: unknown[]) => Promise<unknown>> = {
    getHealth: () => ok(mock.mockHealth),
    getNews: () => ok({ items: mock.mockNews, next_cursor: null }),
    getNewsFeedLayout: () => ok(mock.mockNewsFeedLayout),
    getNewsEventDetail: (key) => ok(mock.mockNewsEventDetails[key as string] ?? firstOf(mock.mockNewsEventDetails)),
    getNewsDetail: (id) => ok(mock.mockNewsDetails[id as number] ?? firstOf(mock.mockNewsDetails)),
    getNewsAnalysis: (id) => ok(mock.mockNewsAnalyses[id as number] ?? null),
    getNewsRuntime: () => ok(mock.mockNewsRuntimeStatus),
    getLlmConfig: () => ok(mock.mockLlmConfig),
    getAllLlmConfigs: () => ok(mock.mockLlmConfigs),
    getLlmStats: () =>
      ok({
        overall: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
        models: [],
        operations: [],
        daily: [],
      }),
    getMarketSnapshots: () => ok(mock.mockMarketSnapshots),
    getWatchlistQuotes: () => ok(mock.mockWatchlistQuotes),
    getStockQuoteDetail: (symbol) => ok(mock.mockStockQuoteDetails[symbol as string] ?? firstOf(mock.mockStockQuoteDetails)),
    getStockKline: (symbol) => ok(mock.mockStockKlines[symbol as string] ?? firstOf(mock.mockStockKlines)),
    getWatchlistSparklines: (symbols) =>
      ok(
        Object.fromEntries(
          (symbols as string[]).map((symbol) => [symbol, mock.mockWatchlistSparklines[symbol] ?? { prices: [] }]),
        ),
      ),
    getCalendar: () => ok({ events: [], skipped_count: 0, window_days: 30, symbol_count: 0, generated_at: iso() }),
    getSymbolCalendar: () => ok({ events: [], skipped_count: 0, window_days: 90, symbol_count: 0, generated_at: iso() }),
    getWatchlist: () => ok(mock.mockWatchlist),
    getWatchlistCandidates: () => ok(mock.mockWatchlistCandidates),
    getRelatedNews: (symbol) => ok(mock.mockRelatedNews[symbol as string] ?? []),
    getWatchlistResearchBrief: (symbol) =>
      ok(mock.mockWatchlistResearchBriefs[symbol as string] ?? firstOf(mock.mockWatchlistResearchBriefs)),
    getWatchlistAiInsight: (symbol) =>
      ok(mock.mockWatchlistAiInsights[symbol as string] ?? { symbol, insight_text: 'mock', generated_at: iso() }),
    getTopics: () => ok(mock.mockTopics),
    getTopicDetail: (id) => ok(mock.mockTopicDetails[id as number] ?? firstOf(mock.mockTopicDetails)),
    getStreamStatus: () => ok(mock.mockStreamStatus),
    getBacktestSummary: () => ok(null),
    getOpsHealth: () => ok(null),
    getXHealth: () => ok(mock.mockXHealth),
    getXAccounts: () => ok(mock.mockXAccounts),
    getXRadar: () => ok(mock.mockXRadar),
    getXPosts: () => ok(mock.mockXPosts),
    getXSearchResults: () => ok([]),
    getFeishuConfig: () => ok(mock.mockFeishuConfig),
    getLatestDigest: () => ok({ available: false, digest: null }),
  };

  const apiClient = new Proxy(explicit, {
    get(target, prop: string) {
      if (prop in target) {
        return target[prop];
      }
      // 兜底：任何未显式 mock 的方法（写操作/未来新增端点）返回空数据即可，
      // 视图在挂载阶段不会调用它们，保持冒烟测试对新增 API 的韧性。
      return () => ok(null);
    },
  });

  return { apiClient };
});

type Anchor = { kind: 'role'; value: string } | { kind: 'text'; value: string };

interface SmokeRoute {
  path: string;
  label: string;
  anchor: Anchor;
}

// 全部无参主模块（导航侧栏可直达的模块）。
const primaryModules: SmokeRoute[] = [
  { path: '/news', label: 'NewsFeed', anchor: { kind: 'text', value: 'Latest Events' } },
  { path: '/dashboard', label: 'Dashboard', anchor: { kind: 'text', value: 'Dashboard' } },
  { path: '/watchlist', label: 'Watchlist', anchor: { kind: 'role', value: 'watchlist-dashboard' } },
  { path: '/x-monitor', label: 'XMonitor', anchor: { kind: 'text', value: 'X Radar' } },
  { path: '/calendar', label: 'Calendar', anchor: { kind: 'role', value: 'calendar-view' } },
  { path: '/settings/llm', label: 'LlmSettings', anchor: { kind: 'text', value: 'LLM Settings' } },
  { path: '/settings/notify', label: 'NotifySettings', anchor: { kind: 'text', value: '通知推送设置' } },
  { path: '/chat', label: 'Chat', anchor: { kind: 'text', value: 'AI 对话助手' } },
  { path: '/digest', label: 'Digest', anchor: { kind: 'text', value: '每日盘前/盘后 AI 简报' } },
  { path: '/analytics/backtest', label: 'SignalBacktest', anchor: { kind: 'text', value: 'Signal Backtest' } },
  { path: '/ops', label: 'OpsHealth', anchor: { kind: 'role', value: 'ops-health-view' } },
  { path: '/portfolio', label: 'Portfolio', anchor: { kind: 'role', value: 'portfolio-view' } },
  { path: '/eval/sentiment', label: 'SentimentEval', anchor: { kind: 'text', value: 'Sentiment Eval' } },
];

// 带参路由用示例参数补充覆盖（参数取自 ../api/mock 里存在的良性夹具）。
const parameterizedModules: SmokeRoute[] = [
  { path: '/news/events/topic-504', label: 'EventDetail', anchor: { kind: 'role', value: 'event-detail-back' } },
  { path: '/news/101', label: 'NewsDetail', anchor: { kind: 'text', value: 'News Detail' } },
  { path: '/news/sentiment/positive', label: 'SentimentNews', anchor: { kind: 'text', value: '新闻' } },
  { path: '/watchlist/0700.HK', label: 'WatchlistDetail', anchor: { kind: 'role', value: 'watchlist-detail-main' } },
  { path: '/topics/501', label: 'TopicDetail', anchor: { kind: 'text', value: 'Topic Detail' } },
];

const allModules = [...primaryModules, ...parameterizedModules];

// 反复 flush 微任务 + nextTick，把「懒加载视图解析 → 挂载 → onMounted 里链式的
// 若干 apiClient 调用 → 再渲染」全部推进到静止，保证断言时视图已完成首屏渲染。
async function settle(): Promise<void> {
  for (let index = 0; index < 8; index += 1) {
    await flushPromises();
    await nextTick();
  }
}

let router: Router;
let wrapper: VueWrapper;

describe('全应用导航冒烟：逐个模块渲染且不触发错误边界', () => {
  beforeAll(async () => {
    // localStorage/sessionStorage 的可用性由 vitest.setup.ts 全局兜底（应对 Node 22+
    // 实验性全局 storage 抛错的环境）。这里只补 jsdom 未实现的观察器：
    // NewsFeedView 会无条件 new IntersectionObserver，图表 resize 会（有守卫地）用
    // ResizeObserver。提供空实现避免误崩。
    class NoopObserver {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
      takeRecords = vi.fn(() => []);
    }
    vi.stubGlobal('IntersectionObserver', NoopObserver);
    vi.stubGlobal('ResizeObserver', NoopObserver);

    // 现在再拉起真实路由表与真实错误边界（此时 storage 已安全）。
    router = (await import('../router')).default;
    const RouteErrorBoundary = (await import('../components/common/RouteErrorBoundary.vue')).default;

    // 与生产一致的组合：<RouteErrorBoundary><RouterView/></RouteErrorBoundary>。
    // RouterView 由 router 插件全局注册，模板里直接使用即可。
    const Shell = defineComponent({
      name: 'SmokeShell',
      components: { RouteErrorBoundary },
      template: '<RouteErrorBoundary><RouterView /></RouteErrorBoundary>',
    });

    setActivePinia(createPinia());
    const pinia = createPinia();

    await router.push('/news');
    await router.isReady();

    wrapper = mount(Shell, { global: { plugins: [pinia, router] } });
    await settle();
  });

  afterAll(() => {
    wrapper?.unmount();
    vi.unstubAllGlobals();
  });

  it('路由表里每个无参主模块都被冒烟列表覆盖（新增模块时提醒同步）', () => {
    const staticModulePaths = router
      .getRoutes()
      .map((record) => record.path)
      .filter((path) => path !== '/' && !path.includes(':'))
      .sort();
    const covered = primaryModules.map((route) => route.path).sort();
    expect(covered).toEqual(staticModulePaths);
  });

  it.each(allModules)('模块 $label（$path）能渲染且不触发错误边界', async (route) => {
    await router.push(route.path);
    await settle();

    // 导航确实落到目标路由。
    expect(router.currentRoute.value.path).toBe(route.path);

    // 关键回归断言：该视图没有崩进错误边界。
    const boundary = wrapper.find('[data-role="route-error-boundary"]');
    expect(boundary.exists(), `${route.label} 触发了 RouteErrorBoundary（切换模块崩溃回归）`).toBe(false);

    // 该视图渲染出了可辨识的内容。
    if (route.anchor.kind === 'role') {
      const node = wrapper.find(`[data-role="${route.anchor.value}"]`);
      expect(node.exists(), `${route.label} 未渲染出 data-role="${route.anchor.value}"`).toBe(true);
    } else {
      expect(wrapper.text(), `${route.label} 未渲染出可辨识文本「${route.anchor.value}」`).toContain(route.anchor.value);
    }
  });
});
