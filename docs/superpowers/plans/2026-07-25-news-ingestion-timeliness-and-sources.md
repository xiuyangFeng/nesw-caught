# 新闻抓取时效性修复 + 信息源扩容 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让新闻抓取常驻运行且更及时，并新增 9 个实测可用的美股新闻通讯社/中文财经快讯信息源。

**Architecture:** 完全复用既有的 `NewsIngestScheduler` + `ingestion/{sources,fetcher,parser}.py` 抓取管线，不引入新组件。新增一个 JSON 解析器 `_parse_wallstreetcn_live_json`（与既有 `_parse_zhipu_news_inline_json` 同构），在 `_default_sources()` 里追加 9 条 `SourceDefinition`，并把"快讯层"源的 `cadence_seconds` 调低到 100s。最后通过本地 `.env` 打开 `NEWS_SCHEDULER_ENABLED`，让调度器随后端进程常驻运行。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / pytest / httpx（通过既有 `http_pool` 共享客户端）/ BeautifulSoup

## Global Constraints

- 不修改 `backend/app/core/config.py` 里 `news_scheduler_enabled` 的代码默认值（保持 `False`），只通过本地 `.env` 开启。
- 新增源一律走 `_default_sources()` 硬编码（不使用 `news_sources_file` JSON 机制），与现有 7 个源保持同一约定。
- 新解析器复用 `source_type="html"` + 自定义 `parser` 字符串这一既有模式（对照 `zhipu_news_inline_json`），不改动 `_validate_source_definition`。
- 测试运行命令：`conda run -n news-caught pytest backend/tests -q`（项目 conda 环境名固定为 `news-caught`）。
- 每个任务完成后按 AGENTS.md 要求回填 `docs/code-change-log.md`（最后一个任务统一回填一次即可，因为三个任务是同一功能闭环）。

---

## 文件结构总览

| 文件 | 改动类型 | 职责 |
|---|---|---|
| `backend/app/services/ingestion/parser.py` | 修改 | 新增 `_parse_wallstreetcn_live_json` 函数 + 顶部新增 `datetime`/`UTC` import |
| `backend/app/services/ingestion/fetcher.py` | 修改 | parser 分发链新增一个 `elif` 分支 |
| `backend/app/services/news_ingestion.py` | 修改 | 把新解析器函数加入模块级 re-export 的 import 列表（供测试直接 `from app.services.news_ingestion import _parse_wallstreetcn_live_json`） |
| `backend/app/services/ingestion/sources.py` | 修改 | `_default_sources()` 追加 9 条新源；既有 CLS Telegraph 条目补上 `cadence_seconds=100` |
| `backend/tests/test_news_ingestion.py` | 修改 | 新增新解析器的单测 + `_default_sources()` 校验测试；import 列表追加 `_parse_wallstreetcn_live_json` |
| `.env`（仓库根目录，本地文件，不进版本库） | 修改 | 追加 `NEWS_SCHEDULER_ENABLED=true` |
| `docs/code-change-log.md` | 修改 | 回填本次变更记录（AGENTS.md 强制要求） |

---

### Task 1: 新增 `wallstreetcn_live_json` 解析器

**Files:**
- Modify: `backend/app/services/ingestion/parser.py`（在 `_parse_zhipu_news_inline_json` 之后追加新函数；顶部 import 区追加 `from datetime import UTC, datetime`）
- Modify: `backend/app/services/ingestion/fetcher.py:96-97`（parser 分发链新增分支）
- Modify: `backend/app/services/news_ingestion.py:17-24`（re-export import 列表追加 `_parse_wallstreetcn_live_json`）
- Test: `backend/tests/test_news_ingestion.py`

**Interfaces:**
- Consumes：`app.services.ingestion.types.SourceDefinition`、`SourceItem`（已存在）；`app.services.ingestion.utils._clean_text`、`_canonicalize_url`（已存在，parser.py 顶部已 import）。
- Produces：`_parse_wallstreetcn_live_json(content: str, source: SourceDefinition) -> list[SourceItem]`，供 `fetcher.py` 与测试调用。

- [ ] **Step 1: 在测试文件里新增三个失败测试**

打开 `backend/tests/test_news_ingestion.py`，把 import 列表（第 21-32 行）里的

```python
from app.services.news_ingestion import (
    NewsIngestionService,
    RefreshSummary,
    SourceDefinition,
    SourceItem,
    _parse_anchor_list_html,
    _parse_minimax_detail_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_zhipu_news_inline_json,
    load_sources,
)
```

改成（新增 `_parse_wallstreetcn_live_json`，按字母序插入）：

```python
from app.services.news_ingestion import (
    NewsIngestionService,
    RefreshSummary,
    SourceDefinition,
    SourceItem,
    _parse_anchor_list_html,
    _parse_minimax_detail_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_wallstreetcn_live_json,
    _parse_zhipu_news_inline_json,
    load_sources,
)
```

然后紧跟在 `test_parse_zhipu_inline_json_source_items`（现第 204-225 行）之后插入三个新测试函数：

```python
def test_parse_wallstreetcn_live_json_uses_title_when_present() -> None:
    payload = json.dumps(
        {
            "code": 20000,
            "data": {
                "items": [
                    {
                        "id": 3777927,
                        "uri": "https://wallstreetcn.com/articles/3777927",
                        "title": "特朗普宣布再次竞选总统",
                        "content": "<p>正文 html</p>",
                        "content_text": "正文纯文本",
                        "display_time": 1700000000,
                    }
                ]
            },
        }
    )
    source = SourceDefinition(
        name="Wallstreetcn Live",
        source_type="html",
        url="https://api-one-wscn.awtmt.com/apiv1/content/lives",
        market="cn",
        parser="wallstreetcn_live_json",
    )

    items = _parse_wallstreetcn_live_json(payload, source)

    assert len(items) == 1
    assert items[0].title == "特朗普宣布再次竞选总统"
    assert items[0].canonical_url == "https://wallstreetcn.com/articles/3777927"
    assert items[0].content_text == "正文纯文本"
    assert items[0].content_html == "<p>正文 html</p>"
    assert items[0].published_at == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)


def test_parse_wallstreetcn_live_json_falls_back_to_content_text_when_title_missing() -> None:
    payload = json.dumps(
        {
            "code": 20000,
            "data": {
                "items": [
                    {
                        "id": 3139744,
                        "uri": "https://wallstreetcn.com/livenews/3139744",
                        "title": "",
                        "content": "<p>沙特主导的联盟继续实施军事行动。</p>",
                        "content_text": "沙特主导的联盟继续实施军事行动，袭击也门胡塞武装的供应和军事场所，多国紧急谴责此次行动导致地区局势进一步升级紧张。（也门电视台快讯）",
                        "display_time": 1721900000,
                    }
                ]
            },
        }
    )
    source = SourceDefinition(
        name="Wallstreetcn Live",
        source_type="html",
        url="https://api-one-wscn.awtmt.com/apiv1/content/lives",
        market="cn",
        parser="wallstreetcn_live_json",
    )

    items = _parse_wallstreetcn_live_json(payload, source)

    assert len(items) == 1
    assert items[0].title == "沙特主导的联盟继续实施军事行动，袭击也门胡塞武装的供应和军事场所，多国紧急谴责此次行动导致地区局势进一步升级紧张。（也门"
    assert len(items[0].title) == 60
    assert items[0].published_at == datetime(2024, 7, 25, 9, 33, 20, tzinfo=UTC)


def test_parse_wallstreetcn_live_json_skips_records_missing_id_or_uri() -> None:
    payload = json.dumps(
        {
            "code": 20000,
            "data": {
                "items": [
                    {"id": None, "uri": "https://wallstreetcn.com/livenews/1", "title": "缺 id", "content_text": "x"},
                    {"id": 2, "uri": None, "title": "缺 uri", "content_text": "x"},
                    {"id": 3, "uri": "https://wallstreetcn.com/livenews/3", "title": "", "content_text": ""},
                ]
            },
        }
    )
    source = SourceDefinition(
        name="Wallstreetcn Live",
        source_type="html",
        url="https://api-one-wscn.awtmt.com/apiv1/content/lives",
        market="cn",
        parser="wallstreetcn_live_json",
    )

    items = _parse_wallstreetcn_live_json(payload, source)

    assert items == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k wallstreetcn -v`
Expected: FAIL，报错 `ImportError: cannot import name '_parse_wallstreetcn_live_json'`（因为函数和 re-export 都还不存在）。

- [ ] **Step 3: 在 `parser.py` 里实现解析函数**

在 `backend/app/services/ingestion/parser.py` 顶部 import 区（当前第 1-16 行）追加一行：

```python
from datetime import UTC, datetime
```

（放在 `import html` 之后、`import json` 之前，保持 stdlib import 字母序。）

然后在 `_parse_zhipu_news_inline_json` 函数结束（当前第 308 行 `return items` 之后，`_parse_the_news_api_json` 定义之前）插入：

```python
def _parse_wallstreetcn_live_json(content: str, source: SourceDefinition) -> list[SourceItem]:
    payload = json.loads(content)
    records = payload.get("data", {}).get("items", [])
    if not isinstance(records, list):
        raise ValueError("wallstreetcn live payload is missing data.items array")

    items: list[SourceItem] = []
    for record in records[: source.item_limit]:
        if not isinstance(record, dict):
            continue
        item_id = record.get("id")
        uri = record.get("uri")
        if not item_id or not uri:
            continue

        content_text = _clean_text(record.get("content_text"))
        raw_title = (record.get("title") or "").strip()
        if raw_title:
            title = raw_title
        elif content_text:
            title = content_text[:60]
        else:
            continue

        display_time = record.get("display_time")
        published_at = (
            datetime.fromtimestamp(display_time, tz=UTC)
            if isinstance(display_time, (int, float)) and not isinstance(display_time, bool)
            else None
        )

        items.append(
            SourceItem(
                title=title,
                canonical_url=_canonicalize_url(uri, source.url),
                summary=content_text[:280] if content_text else None,
                content_text=content_text,
                content_html=record.get("content"),
                published_at=published_at,
            )
        )
    return items
```

- [ ] **Step 4: 接入 `fetcher.py` 分发链**

在 `backend/app/services/ingestion/fetcher.py` 里，把当前第 92-97 行：

```python
            elif source.parser == "anchor_list_html":
                items = _parse_anchor_list_html(response.text, source)
            elif source.parser == "zhipu_news_inline_json":
                items = _parse_zhipu_news_inline_json(response.text, source)
            elif source.parser == "selector_html":
                items = _parse_selector_html(response.text, source)
```

改成：

```python
            elif source.parser == "anchor_list_html":
                items = _parse_anchor_list_html(response.text, source)
            elif source.parser == "zhipu_news_inline_json":
                items = _parse_zhipu_news_inline_json(response.text, source)
            elif source.parser == "wallstreetcn_live_json":
                items = _parse_wallstreetcn_live_json(response.text, source)
            elif source.parser == "selector_html":
                items = _parse_selector_html(response.text, source)
```

并在文件顶部 import 区（当前第 7-13 行）把：

```python
from app.services.ingestion.parser import (
    _parse_anchor_list_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_the_news_api_json,
    _parse_zhipu_news_inline_json,
)
```

改成：

```python
from app.services.ingestion.parser import (
    _parse_anchor_list_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_the_news_api_json,
    _parse_wallstreetcn_live_json,
    _parse_zhipu_news_inline_json,
)
```

- [ ] **Step 5: 在 `news_ingestion.py` 里加入 re-export**

把 `backend/app/services/news_ingestion.py` 当前第 17-24 行：

```python
from app.services.ingestion.parser import (
    _parse_anchor_list_html,
    _parse_minimax_detail_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_the_news_api_json,
    _parse_zhipu_news_inline_json,
)
```

改成：

```python
from app.services.ingestion.parser import (
    _parse_anchor_list_html,
    _parse_minimax_detail_html,
    _parse_rss_or_atom,
    _parse_selector_html,
    _parse_the_news_api_json,
    _parse_wallstreetcn_live_json,
    _parse_zhipu_news_inline_json,
)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k wallstreetcn -v`
Expected: 3 个测试全部 PASS。

- [ ] **Step 7: 跑一次全量后端测试，确认没有破坏既有用例**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: 全部通过（新增 3 个用例，总数比之前多 3）。

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/ingestion/parser.py backend/app/services/ingestion/fetcher.py backend/app/services/news_ingestion.py backend/tests/test_news_ingestion.py
git commit -m "feat(backend): 新增华尔街见闻 7x24 快讯 JSON 解析器"
```

---

### Task 2: 扩充 `_default_sources()` 信息源 + cadence 分层

**Files:**
- Modify: `backend/app/services/ingestion/sources.py`（`_default_sources()` 函数，当前第 28-90 行）
- Test: `backend/tests/test_news_ingestion.py`

**Interfaces:**
- Consumes：Task 1 产出的 `parser="wallstreetcn_live_json"` 字符串值（无需 import 函数本身，只是字符串常量）；`app.services.ingestion.sources._default_sources`、`_validate_source_definition`（模块内私有函数，测试里直接从 `app.services.ingestion.sources` import）。
- Produces：`_default_sources()` 返回列表从 7 条扩到 16 条，供 `load_sources()`、调度器、下游所有代码透明使用（无接口签名变化）。

- [ ] **Step 1: 新增失败测试**

在 `backend/tests/test_news_ingestion.py` 末尾追加：

```python
def test_default_sources_are_all_valid_and_unique() -> None:
    from app.services.ingestion.sources import _default_sources, _validate_source_definition

    sources = _default_sources()

    assert len(sources) == 16
    names = [source.name for source in sources]
    assert len(names) == len(set(names)), f"duplicate source names: {names}"
    for source in sources:
        _validate_source_definition(source)

    by_name = {source.name: source for source in sources}
    expected_flash_tier = {
        "CLS Telegraph": 100,
        "MarketWatch MarketPulse": 100,
        "Wallstreetcn Live": 100,
    }
    for name, expected_cadence in expected_flash_tier.items():
        assert by_name[name].cadence_seconds == expected_cadence, name

    wallstreetcn = by_name["Wallstreetcn Live"]
    assert wallstreetcn.parser == "wallstreetcn_live_json"
    assert wallstreetcn.source_type == "html"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k test_default_sources_are_all_valid_and_unique -v`
Expected: FAIL（`assert 7 == 16` 或 `KeyError: 'MarketWatch MarketPulse'`）。

- [ ] **Step 3: 修改 `_default_sources()`**

在 `backend/app/services/ingestion/sources.py` 里，把既有 CLS Telegraph 条目（当前第 58-70 行）：

```python
        SourceDefinition(
            name="CLS Telegraph",
            source_type="html",
            url="https://www.cls.cn/telegraph",
            market="cn",
            language="zh",
            parser="selector_html",
            entry_selector="div.p-t-20.p-b-20.b-b-w-1",
            title_selector=".telegraph-content-box .c-34304b",
            link_selector="a[href^='/detail/']",
            time_selector=".telegraph-time-box",
            content_selector=".telegraph-content-box .c-34304b",
        ),
```

改成（补上 `cadence_seconds=100`，纳入快讯层）：

```python
        SourceDefinition(
            name="CLS Telegraph",
            source_type="html",
            url="https://www.cls.cn/telegraph",
            market="cn",
            language="zh",
            parser="selector_html",
            cadence_seconds=100,
            entry_selector="div.p-t-20.p-b-20.b-b-w-1",
            title_selector=".telegraph-content-box .c-34304b",
            link_selector="a[href^='/detail/']",
            time_selector=".telegraph-time-box",
            content_selector=".telegraph-content-box .c-34304b",
        ),
```

然后在 `_default_sources()` 返回列表的最后一个元素（Zhipu AI News，当前第 81-89 行）之后、闭合 `]` 之前，追加 9 条新定义：

```python
        SourceDefinition(
            name="MarketWatch Top Stories",
            source_type="rss",
            url="http://feeds.marketwatch.com/marketwatch/topstories/",
            market="us",
            language="en",
        ),
        SourceDefinition(
            name="MarketWatch MarketPulse",
            source_type="rss",
            url="http://feeds.marketwatch.com/marketwatch/marketpulse/",
            market="us",
            language="en",
            cadence_seconds=100,
        ),
        SourceDefinition(
            name="CNBC Finance",
            source_type="rss",
            url="https://www.cnbc.com/id/100003114/device/rss/rss.html",
            market="us",
            language="en",
        ),
        SourceDefinition(
            name="Yahoo Finance News",
            source_type="rss",
            url="https://finance.yahoo.com/news/rssindex",
            market="us",
            language="en",
        ),
        SourceDefinition(
            name="PR Newswire Financial Services",
            source_type="rss",
            url="https://www.prnewswire.com/rss/financial-services-latest-news/financial-services-latest-news-list.rss",
            market="us",
            language="en",
        ),
        SourceDefinition(
            name="GlobeNewswire Earnings",
            source_type="rss",
            url="https://www.globenewswire.com/RssFeed/subjectcode/9-Earnings%20Releases%20and%20Operating%20Results/feedTitle/GlobeNewswire%20-%20Category%20News",
            market="us",
            language="en",
        ),
        SourceDefinition(
            name="Nasdaq Press Releases",
            source_type="rss",
            url="https://www.nasdaq.com/feed/rssoutbound?category=Press-Release",
            market="us",
            language="en",
        ),
        SourceDefinition(
            name="Investing.com CN",
            source_type="rss",
            url="https://cn.investing.com/rss/news.rss",
            market="cn",
            language="zh",
        ),
        SourceDefinition(
            name="Wallstreetcn Live",
            source_type="html",
            url="https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&client=pc&limit=20",
            market="cn",
            language="zh",
            parser="wallstreetcn_live_json",
            cadence_seconds=100,
        ),
```

- [ ] **Step 4: 运行测试确认通过**

Run: `conda run -n news-caught pytest backend/tests/test_news_ingestion.py -k test_default_sources_are_all_valid_and_unique -v`
Expected: PASS。

- [ ] **Step 5: 跑一次全量后端测试**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: 全部通过。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ingestion/sources.py backend/tests/test_news_ingestion.py
git commit -m "feat(backend): 新增 9 个美股/中文财经信息源，CLS/MarketPulse/Wallstreetcn 纳入快讯层 cadence"
```

---

### Task 3: 开启常驻抓取 + 端到端验证 + 回填变更记录

**Files:**
- Modify: `.env`（仓库根目录，gitignored，不提交）
- Modify: `docs/code-change-log.md`

**Interfaces:**
- Consumes：Task 1、Task 2 的全部产出（16 个源、新解析器）；`backend/app/main.py` 已有的 `if settings.news_scheduler_enabled: news_scheduler.start()` 生命周期挂载逻辑（无需改动）。
- Produces：无新代码接口；产出的是一次可观察的真实抓取运行结果，写入 `docs/code-change-log.md`。

- [ ] **Step 1: 打开本地调度器开关**

打开仓库根目录的 `.env` 文件，在文件末尾追加一行：

```
NEWS_SCHEDULER_ENABLED=true
```

（若该文件不存在同名 key，直接追加；若已存在但为其他值，改成 `true`。）

- [ ] **Step 2: 重启本地开发服务并观察调度器启动日志**

Run: `./scripts/dev.sh`（或用户已有的常规启动方式）

启动完成后，检查后端日志（`backend/data/logs/backend.log`）里出现：

```
Worker 'news_ingest_scheduler' started
```

Expected: 能找到这一行，说明调度器已随进程启动（对照 `backend/app/workers/base_worker.py:49` 的日志格式）。

- [ ] **Step 3: 手动跑一次全量抓取，确认新源可用**

Run: `make ingest-news`
Expected: 输出里能看到 16 个源各自的 `status=ok`（或至少不是全部 `http_error`/`parse_error`）；重点确认新增的 9 个源里，`Wallstreetcn Live` 与 `Investing.com CN` 至少有 `inserted_count > 0` 或 `status=ok`（RSS 类源若命中已抓取过的旧数据可能是 `status=empty`，属正常）。

如果某个源返回 `http_error`/`parse_error`：记录下来（不阻塞其他任务），后续作为已知风险写进 `docs/code-change-log.md` 的"风险或后续事项"，不需要在本次任务里修复（外部网站结构变化是长期存在的运维问题，不是本次实现的 bug）。

- [ ] **Step 4: 跑全量后端测试做最终回归确认**

Run: `conda run -n news-caught pytest backend/tests -q`
Expected: 全部通过。

- [ ] **Step 5: 回填 `docs/code-change-log.md`**

在文件末尾追加一条新记录（按文件里现有的模板格式），至少包含：

- 日期：2026-07-25
- 修改人：Claude
- 修改范围：新闻抓取时效性修复、信息源扩容
- 变更内容：（用事实描述本次三个任务分别做了什么——常驻调度开关、cadence 分层、9 个新源、新解析器）
- 影响文件：列出 Task 1/2 表格里的全部文件 + `.env`
- 接口/数据结构变化：无（`SourceDefinition`/`SourceItem` 结构未变，只是新增数据和一个内部解析器）
- 验证情况：写实际跑出来的 `conda run -n news-caught pytest backend/tests -q` 结果，以及 Step 3 里 `make ingest-news` 的真实抓取结果摘要
- 风险或后续事项：Step 3 里如果有源抓取失败，写在这里；另外写明东方财富/格隆汇/AAStocks/同花顺等候选已评估但本次未接入的原因（对照设计文档 `docs/superpowers/specs/2026-07-25-news-ingestion-timeliness-and-sources-design.md` 第 3.3 节）

- [ ] **Step 6: Commit**

```bash
git add docs/code-change-log.md
git commit -m "docs: 回填新闻抓取时效性修复 + 信息源扩容变更记录"
```

（`.env` 本身不 commit，已被 `.gitignore` 忽略。）

---

## 完成标准

- [ ] Task 1、2、3 全部完成，三次独立 commit。
- [ ] `conda run -n news-caught pytest backend/tests -q` 全绿。
- [ ] `make ingest-news` 实测输出显示 16 个源参与抓取，多数状态正常。
- [ ] `docs/code-change-log.md` 已回填。
