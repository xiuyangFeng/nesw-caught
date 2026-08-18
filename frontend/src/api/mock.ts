// mock.ts 是前端离线/降级模式下所有业务域 mock 数据的统一出口（薄聚合层）。
//
// 实际数据按业务域拆分到 ./mock/ 目录下的子模块中：
//   - mock/shared.ts      公共时间基准与格式化工具（内部使用，未对外导出）
//   - mock/news.ts        新闻、话题(Topic)、事件流(NewsFeedLayout)
//   - mock/market.ts      行情快照、自选股(Watchlist)、K 线、研究简报
//   - mock/llm.ts         LLM 配置、翻译、新闻个股映射分析、AI 投研简报
//   - mock/xMonitor.ts    X（Twitter）监控：账号、帖子、情报雷达
//   - mock/ops.ts         系统健康检查、SSE 流、飞书通知、新闻链路运行时状态
//   - mock/marketOverview.ts  市场总览(五市场聚合 + 指数配置清单)
//   - mock/sentimentEval.ts 情绪/利好利空评测闭环（GET/POST /api/eval/sentiment[/run]）
//   - mock/sentimentTimeline.ts 个股情绪时间线 + 背离提醒（GET /api/watchlist/{symbol}/sentiment-timeline）
//
// 本文件只做 re-export，不新增/修改任何数据，保证所有既有 `from './mock'` /
// `from '../api/mock'` 的导入路径与签名保持 100% 不变。
export * from './mock/news';
export * from './mock/market';
export * from './mock/llm';
export * from './mock/xMonitor';
export * from './mock/ops';
export * from './mock/marketOverview';
export * from './mock/sentimentEval';
export * from './mock/sentimentTimeline';
export * from './mock/quant';
