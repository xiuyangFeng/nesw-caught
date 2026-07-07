# 2026-06-13 新闻源与前端交互“丝滑度”优化设计

## 1. 目标与背景
为了让 `news-caught` 项目不仅在底层安全，在数据摄入效率和前端用户体验（UX）上同样具备高级、丝滑的现代 Web 质感，本次优化拟实现以下两大方向：
1. **数据源网络拉取极致优化**：支持 HTTP 304 缓存感知，优化大文件 RSS 重复抓取和解析开销，并设计异步后台正文智能爬虫。
2. **前端视觉与交互平滑化**：包括 AI 聊天打字机缓动渲染、智能触底滚动锁、1:1 高科技呼吸骨架屏和增量新闻加载浮条。

---

## 2. 详细设计

### 2.1 后端 HTTP 304 缓存感知
- **背景**：大量源（如 sec.gov、WSJ 等）每次拉取都返回几百 KB 的 XML 报文，但实际上大部分时候并没有新文章发布。重复下载解析既费时又消耗资源。
- **设计**：
  1. 在 `source_health` 表中新增 `last_etag` 和 `last_modified`。
  2. `fetch_source_items` 传入 `SourceDefinition`，获取时先从 `source_health` 查出上次保存的 ETag 和 Last-Modified。
  3. 使用 `httpx` 发起请求，并在 Headers 中设置 `If-None-Match: <etag>` 与 `If-Modified-Since: <last_modified>`。
  4. 如果响应是 304 Not Modified，则直接标记成功，不再继续流式读取或解析内容，列表为空。
  5. 如果是 200 OK，正常解析并在保存结果时，从 `response.headers` 里提取 `ETag` 和 `Last-Modified` 回填更新数据库，以便下次生效。

### 2.2 异步网页正文智能提取
- **背景**：很多 RSS 只给出两句摘要。AI 对话和生成报告需要真实文章内容作为准确上下文。
- **设计**：
  1. 编写 `app/services/ingestion/article_crawler.py`。
  2. 实现 `crawl_and_extract_article(url)`：使用 `httpx` 获取原文页面，通过去除 `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>` 以及侧边栏等标签，对正文所在的标签节点（例如计算文字密度和段落数最大的节点，或是常见新闻网的正文通用选择器）提取出纯文本内容。
  3. 在 `QueueWorker` 队列中：当新入库的新闻被检测到只有摘要而无正文时，异步触发此爬虫，将抽取的纯净正文保存入 `article_content` 表的 `content_text` 字段，以无感的方式强化本地投研知识库。

### 2.3 AI 聊天平滑打字机与滚动锁 (Smart Typing & Pinning)
- **设计**：
  1. **平滑打字机效果**：在 `ChatView.vue` 中，当流式数据包通过 SSE 快速或不均匀地到达时，前端将其暂存至缓冲区。利用 `requestAnimationFrame` 或 25ms 间隔的定时器，平滑且匀速地将字符显示到 UI 上，让流式展现更加像人眼阅读的自然流动，消除闪跳。
  2. **智能触底滚动锁 (Scroll Pinning)**：
     - 前端渲染线程会维持一个 `shouldAutoScroll` 的布尔值，在流式生成中若为 `true`，则自动执行 `element.scrollTop = element.scrollHeight`。
     - 监听对话视口的 `scroll` 事件。若用户进行了手势上滚，或滚轮向上，或者 `scrollTop` 偏离底部的距离大于 60 像素，则自动把 `shouldAutoScroll` 设为 `false`，停止强制拉动滚动条。
     - 此时在右下角以半透明毛玻璃特效淡入淡出一个 “⬇ 有新回复，点击回到底部” 的悬浮按钮，并带呼吸小点。
     - 用户点击按钮或手动再次拉到接近底部（距底小于 20 像素），则重新设 `shouldAutoScroll` 为 `true`，并隐藏按钮。

### 2.4 全屏幕呼吸发光骨架屏过渡 (Shimmering Skeleton)
- **设计**：
  - 设计 `<SkeletonFeed>` 组件：通过纯 CSS 自绘出跟新闻列表、仪表盘卡片、自选股列表 1:1 的占位形状，并增加 `@keyframes shimmer` 背景发光扫过的流畅动效。
  - 在 Vue 的路由切换或数据加载状态 `loading` 为 `true` 时展示骨架屏。当 `loading` 转为 `false` 后，使用 Vue 的 `<transition name="fade-cross">`，通过 CSS 动画实现骨架屏 `opacity` 渐变淡出，真实内容淡入，交叉时长为 300ms。

### 2.5 增量数据更新提示浮条 (Delta Banner)
- **设计**：
  - 在 `NewsFeedView.vue` 界面中，当用户正在滑动阅读新闻时，如果后台又有新的抓取任务成功落库并通过 SSE 推送了新文章：
    - 我们不自动刷新列表（防止正在阅读的行被瞬间推走引发的眩晕感）。
    - 我们在顶部浮现一个高斯模糊霓虹发光的浮条：“💡 发现 x 条新资讯，点击更新”。
    - 点击此浮条后，前端平滑地将这些新新闻展开并加入到当前列表最顶部，并将视口平顺地过渡对齐。
