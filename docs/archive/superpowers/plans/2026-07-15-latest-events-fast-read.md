# Latest Events 快读改版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「最新事件」板块改造为快读优先：事件/主题压成顶部紧凑条、新闻卡片带 AI 一句话结论与视觉分级、就地抽屉阅读 + 键盘流 + 已读淡化 + 低分折叠，后端补 `ai_takeaway` 字段与生成管线并提速详情接口。

**Architecture:** 后端在 `news_item` 加 `ai_takeaway` 列，走两条生成路径（分类器 LLM 精修顺路产出 + feed layout 后台补齐 worker），通过既有 `news.updated` / `news.signals_processed` 事件驱动前端增量与缓存失效。前端新增紧凑条组件、已读/折叠/键盘三个独立工具模块，最后在 NewsFeedView 一次集成并复用 Dashboard 的 NewsDetailDrawer。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + SQLite（后端）；Vue 3.5 + TS + Pinia + Vitest + @vue/test-utils（前端）。

**Spec:** `docs/superpowers/specs/2026-07-15-latest-events-fast-read-design.md`

## Global Constraints

- 后端测试命令：`conda run -n news-caught pytest backend/tests -q`（不是 venv；单个文件加路径即可）。
- 前端命令都在 `frontend/` 下跑：`npm run test -- --run <file>`、`npm run typecheck`（脚本已带 `-p tsconfig.app.json`，不可省）、`npm run generate:api`、`npm run check:api-drift`。
- **红涨绿跌**：`--positive: #ff5a72`（红=利好）、`--negative: #1fd39a`（绿=利空）。不要按欧美习惯反过来。
- 情绪 pill 既有 class：`.pill.positive/.negative/.neutral/.mixed/.unknown`；令牌在 `frontend/src/assets/main.css`。
- 后端 `sentiment_label` 是可空普通 string，不是枚举。
- 注释/文案用中文，风格与周边代码一致；commit message 用中文 conventional 风格（如 `feat(frontend): …`）。
- 每个任务只允许改动自己 **Files** 清单里的文件（多智能体并行，文件范围互不重叠）。
- 迁移采用防御式幂等写法（列存在则跳过），模板见 `backend/alembic/versions/b8e4d7f2a9c1_add_watchlist_position_and_cost.py`。

## 并行波次

| 波次 | 任务 | 依赖 |
| --- | --- | --- |
| Wave 1（5 个并行） | T1 后端契约、T2 详情提速、T3 已读+折叠工具、T4 键盘 composable、T5 紧凑条组件 | 无 |
| Wave 2（3 个并行） | T6 分类器顺路 takeaway、T7 补齐 worker、T8 NewsCard 改造 | T6/T7 依赖 T1；T8 依赖 T1+T3 |
| Wave 3（串行） | T9 NewsFeedView 集成 | 全部 |
| Wave 4 | T10 全量验证（主会话执行） | T9 |

---

### Task 1: 后端契约 — ai_takeaway 列 + Schema + 前端类型再生成

**Files:**
- Create: `backend/alembic/versions/c4f8a1d3e6b2_add_news_ai_takeaway.py`
- Modify: `backend/app/models/news_item.py`
- Modify: `backend/app/schemas/news.py`（`NewsItemSummary`，第 6-16 行）
- Create: `backend/tests/test_ai_takeaway_contract.py`
- Regenerate: `frontend/src/types/generated/api.d.ts` + `frontend/openapi.json`（跑脚本生成，勿手改）

**Interfaces:**
- Produces: `NewsItem.ai_takeaway: Mapped[str | None]`；`NewsItemSummary.ai_takeaway: str | None = None`；前端 `NewsItem`/`NewsDetail` 类型自动获得 `ai_takeaway?: string | null`。T6/T7/T8 依赖本任务。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_ai_takeaway_contract.py`：

```python
from datetime import datetime, timezone

import sqlalchemy as sa

from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.schemas.news import NewsItemSummary


def test_news_item_table_has_ai_takeaway_column() -> None:
    with SessionLocal() as session:
        inspector = sa.inspect(session.get_bind())
        columns = {column["name"] for column in inspector.get_columns("news_item")}
    assert "ai_takeaway" in columns


def test_news_item_summary_carries_ai_takeaway() -> None:
    with SessionLocal() as session:
        item = NewsItem(
            source_name="UnitTest",
            source_url="https://example.com/takeaway",
            title="takeaway contract",
            canonical_url="https://example.com/takeaway-contract",
            url_hash="hash-takeaway-contract",
            market="us",
            fetched_at=datetime.now(timezone.utc),
            ai_takeaway="测试结论:偏利好",
        )
        session.add(item)
        session.commit()
        try:
            view = NewsItemSummary.model_validate(item, from_attributes=True)
            assert view.ai_takeaway == "测试结论:偏利好"
        finally:
            session.delete(item)
            session.commit()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n news-caught pytest backend/tests/test_ai_takeaway_contract.py -q`
Expected: FAIL（`ai_takeaway` 列不存在 / TypeError: invalid keyword）

- [ ] **Step 3: 模型加列**

`backend/app/models/news_item.py` 在 `summary` 字段（第 21 行）后加：

```python
    ai_takeaway: Mapped[str | None] = mapped_column(Text(), default=None)
```

- [ ] **Step 4: 新建迁移**

创建 `backend/alembic/versions/c4f8a1d3e6b2_add_news_ai_takeaway.py`（down_revision 指向当前 head `b8e4d7f2a9c1`）：

```python
"""add_news_ai_takeaway

Revision ID: c4f8a1d3e6b2
Revises: b8e4d7f2a9c1
Create Date: 2026-07-15 12:00:00.000000

给 news_item 表增加 AI 一句话结论列：
- ai_takeaway（Text，可空）：谁受影响/偏利好利空/原因的一句中文结论。

与 b8e4d7f2a9c1 一致采用防御式幂等写法（列已存在则跳过）。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4f8a1d3e6b2'
down_revision: str | Sequence[str] | None = 'b8e4d7f2a9c1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (defensive / idempotent)."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if 'news_item' not in inspector.get_table_names():
        return
    existing = {column['name'] for column in inspector.get_columns('news_item')}
    if 'ai_takeaway' not in existing:
        with op.batch_alter_table('news_item', schema=None) as batch_op:
            batch_op.add_column(sa.Column('ai_takeaway', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('news_item', schema=None) as batch_op:
        batch_op.drop_column('ai_takeaway')
```

- [ ] **Step 5: Schema 加字段**

`backend/app/schemas/news.py` 的 `NewsItemSummary` 末尾（`editorial_score` 之后）加：

```python
    ai_takeaway: str | None = None
```

- [ ] **Step 6: 跑测试确认通过**

Run: `conda run -n news-caught pytest backend/tests/test_ai_takeaway_contract.py -q`
Expected: 2 passed（conftest 会 `initialize_database()` 自动跑迁移）

- [ ] **Step 7: 再生成前端类型**

Run: `cd frontend && npm run generate:api && npm run check:api-drift`
Expected: 生成成功、drift 检查退出码 0；`grep -n "ai_takeaway" src/types/generated/api.d.ts` 至少命中 NewsItemSummary/NewsDetailView。

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/news_item.py backend/app/schemas/news.py backend/alembic/versions/c4f8a1d3e6b2_add_news_ai_takeaway.py backend/tests/test_ai_takeaway_contract.py frontend/src/types/generated/api.d.ts frontend/openapi.json
git commit -m "feat(backend): news_item 新增 ai_takeaway 列并贯通 schema/前端类型"
```

---

### Task 2: 详情接口提速 — 4 次串行查询合并为 2 次往返

**Files:**
- Modify: `backend/app/repositories/news_repository.py`
- Modify: `backend/app/api/routes/news.py`（`get_news_detail`，第 184-227 行）
- Create: `backend/tests/test_news_detail_bundle.py`

**Interfaces:**
- Produces: `NewsRepository.get_detail_bundle(news_id: int) -> NewsDetailBundle | None`，`NewsDetailBundle(item, article, mentions, topic)` dataclass。响应 schema `NewsDetailView` 不变。
- Consumes: 现有 `list_mentions`；不依赖其他任务。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_news_detail_bundle.py`（seeding/清理模式参照 `backend/tests/test_news.py` 的 feed-layout 测试段）：

```python
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.article_content import ArticleContent
from app.models.news_item import NewsItem
from app.models.news_stock_mention import NewsStockMention
from app.models.topic_cluster import TopicCluster
from app.models.topic_news_link import TopicNewsLink
from app.repositories.news_repository import NewsRepository


def _make_item(session, *, suffix: str) -> NewsItem:
    item = NewsItem(
        source_name="UnitTest",
        source_url=f"https://example.com/{suffix}",
        title=f"bundle {suffix}",
        canonical_url=f"https://example.com/bundle-{suffix}",
        url_hash=f"hash-bundle-{suffix}",
        market="us",
        fetched_at=datetime.now(timezone.utc),
    )
    session.add(item)
    session.flush()
    return item


def test_get_detail_bundle_returns_all_parts() -> None:
    with SessionLocal() as session:
        item = _make_item(session, suffix="full")
        session.add(ArticleContent(news_id=item.id, content_text="正文", extract_status="success"))
        session.add(
            NewsStockMention(news_id=item.id, symbol="NVDA", market="us", mention_type="explicit", confidence=0.9)
        )
        topic = TopicCluster(
            topic_key="bundle-topic", topic_title="Bundle Topic", last_seen_at=datetime.now(timezone.utc)
        )
        session.add(topic)
        session.flush()
        session.add(TopicNewsLink(topic_cluster_id=topic.id, news_id=item.id))
        session.commit()
        try:
            bundle = NewsRepository(session).get_detail_bundle(item.id)
            assert bundle is not None
            assert bundle.item.id == item.id
            assert bundle.article is not None and bundle.article.content_text == "正文"
            assert [m.symbol for m in bundle.mentions] == ["NVDA"]
            assert bundle.topic is not None and bundle.topic.topic_title == "Bundle Topic"
        finally:
            session.rollback()
            for table in ("topic_news_link", "news_stock_mention", "article_content"):
                session.execute(sa.text(f"DELETE FROM {table} WHERE news_id = :v"), {"v": item.id})
            session.execute(sa.text("DELETE FROM topic_cluster WHERE topic_key = 'bundle-topic'"))
            session.delete(session.get(NewsItem, item.id))
            session.commit()


def test_get_detail_bundle_handles_missing_parts() -> None:
    with SessionLocal() as session:
        item = _make_item(session, suffix="bare")
        session.commit()
        try:
            bundle = NewsRepository(session).get_detail_bundle(item.id)
            assert bundle is not None
            assert bundle.article is None
            assert bundle.mentions == []
            assert bundle.topic is None
        finally:
            session.delete(session.get(NewsItem, item.id))
            session.commit()


def test_get_detail_bundle_missing_news_returns_none() -> None:
    with SessionLocal() as session:
        assert NewsRepository(session).get_detail_bundle(987654321) is None


def test_detail_api_shape_unchanged() -> None:
    client = TestClient(app)
    with SessionLocal() as session:
        item = _make_item(session, suffix="api")
        session.commit()
        item_id = item.id
    try:
        response = client.get(f"/api/news/{item_id}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == item_id
        assert payload["mentions"] == []
        assert payload["article"] is None
        assert payload["topic"] is None
    finally:
        with SessionLocal() as session:
            session.delete(session.get(NewsItem, item_id))
            session.commit()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n news-caught pytest backend/tests/test_news_detail_bundle.py -q`
Expected: FAIL（`AttributeError: 'NewsRepository' object has no attribute 'get_detail_bundle'`）

- [ ] **Step 3: 仓库层实现**

`backend/app/repositories/news_repository.py`：文件顶部（imports 之后、`class NewsRepository` 之前）加：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class NewsDetailBundle:
    item: NewsItem
    article: ArticleContent | None
    mentions: list[NewsStockMention]
    topic: TopicCluster | None
```

在 `get_topic_for_news`（第 137-143 行）之后加方法：

```python
    def get_detail_bundle(self, news_id: int) -> NewsDetailBundle | None:
        """详情页聚合读取:item/article/topic 单条 JOIN 查询 + mentions 一次列表查询。

        原实现为 4 次串行查询,SQLite 单 writer 场景下往返次数直接决定
        抽屉打开延迟,故合并为 2 次。
        """
        stmt = (
            select(NewsItem, ArticleContent, TopicCluster)
            .outerjoin(ArticleContent, ArticleContent.news_id == NewsItem.id)
            .outerjoin(TopicNewsLink, TopicNewsLink.news_id == NewsItem.id)
            .outerjoin(TopicCluster, TopicCluster.id == TopicNewsLink.topic_cluster_id)
            .where(NewsItem.id == news_id)
        )
        row = self.session.execute(stmt).first()
        if row is None:
            return None
        item, article, topic = row
        return NewsDetailBundle(
            item=item,
            article=article,
            mentions=self.list_mentions(news_id),
            topic=topic,
        )
```

- [ ] **Step 4: 路由层改用 bundle**

`backend/app/api/routes/news.py` 的 `get_news_detail`（第 184-227 行）整体替换为（imports 处补 `NewsDetailBundle` 不需要——只用返回值属性）：

```python
@router.get("/{news_id}", response_model=NewsDetailView)
def get_news_detail(news_id: int, session: Session = Depends(get_db_session)) -> NewsDetailView:
    repository = NewsRepository(session)
    bundle = repository.get_detail_bundle(news_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="news not found")

    item, article, topic = bundle.item, bundle.article, bundle.topic
    return NewsDetailView(
        **NewsItemSummary.model_validate(item, from_attributes=True).model_dump(),
        sentiment_score=item.sentiment_score,
        article=(
            NewsArticleView(
                content_text=article.content_text,
                extract_status=article.extract_status,
                extract_error=article.extract_error,
                extracted_at=article.extracted_at,
            )
            if article
            else None
        ),
        mentions=[
            NewsMentionView(
                symbol=mention.symbol,
                market=mention.market,
                mention_type=mention.mention_type,
                confidence=mention.confidence,
            )
            for mention in bundle.mentions
        ],
        topic=(
            NewsTopicRefView(
                id=topic.id,
                topic_title=topic.topic_title,
                importance_score=topic.importance_score or 0.0,
                last_seen_at=topic.last_seen_at,
            )
            if topic
            else None
        ),
    )
```

- [ ] **Step 5: 跑测试确认通过 + 回归**

Run: `conda run -n news-caught pytest backend/tests/test_news_detail_bundle.py backend/tests/test_news.py -q`
Expected: 全部 PASS（test_news.py 里的既有详情测试保持绿）

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/news_repository.py backend/app/api/routes/news.py backend/tests/test_news_detail_bundle.py
git commit -m "perf(backend): 详情接口 4 次串行查询合并为 2 次往返"
```

---

### Task 3: 前端已读状态 + 低分折叠工具

**Files:**
- Create: `frontend/src/utils/readNews.ts`
- Create: `frontend/src/utils/readNews.test.ts`
- Create: `frontend/src/utils/newsFolding.ts`
- Create: `frontend/src/utils/newsFolding.test.ts`

**Interfaces:**
- Produces:
  - `isNewsRead(id: number): boolean`、`markNewsRead(id: number): void`、`useReadNewsIds(): ReadonlySet<number>`（reactive Set，可直接放 computed 依赖）、`resetReadNewsForTest(): void`
  - `partitionFoldableStream(entries: EditorialStoryEntry[]): { visible: EditorialStoryEntry[]; folded: EditorialStoryEntry[] }`（入参须已按分数降序，即 `rankEditorialStories` 的输出）
- Consumes: `EditorialStoryEntry`（`frontend/src/utils/newsEditorial.ts`）。T8/T9 消费本任务。

- [ ] **Step 1: 写失败测试（readNews）**

创建 `frontend/src/utils/readNews.test.ts`：

```typescript
import { beforeEach, describe, expect, it } from 'vitest';

import { isNewsRead, markNewsRead, resetReadNewsForTest, useReadNewsIds } from './readNews';

describe('readNews', () => {
  beforeEach(() => {
    resetReadNewsForTest();
  });

  it('标记后 isNewsRead 为 true 且持久化到 localStorage', () => {
    expect(isNewsRead(1)).toBe(false);
    markNewsRead(1);
    expect(isNewsRead(1)).toBe(true);
    expect(JSON.parse(localStorage.getItem('news-caught:read-news-ids') ?? '[]')).toContain(1);
  });

  it('useReadNewsIds 返回响应式集合', () => {
    const ids = useReadNewsIds();
    markNewsRead(42);
    expect(ids.has(42)).toBe(true);
  });

  it('超过 2000 条时 FIFO 淘汰最早的', () => {
    for (let i = 0; i < 2001; i += 1) {
      markNewsRead(i);
    }
    expect(isNewsRead(0)).toBe(false);
    expect(isNewsRead(2000)).toBe(true);
    expect(useReadNewsIds().size).toBe(2000);
  });

  it('重复标记不改变集合大小', () => {
    markNewsRead(7);
    markNewsRead(7);
    expect(useReadNewsIds().size).toBe(1);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npm run test -- --run src/utils/readNews.test.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 readNews.ts**

创建 `frontend/src/utils/readNews.ts`：

```typescript
import { reactive } from 'vue';

const STORAGE_KEY = 'news-caught:read-news-ids';
const MAX_TRACKED = 2000;

// Node22+ 实验性全局 storage 可能抛错,统一防御式获取(与 watchlistChartStore 同模式)
const safeStorage = (() => {
  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
})();

function loadInitial(): number[] {
  try {
    const raw = safeStorage?.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((value): value is number => typeof value === 'number') : [];
  } catch {
    return [];
  }
}

// Set 迭代按插入顺序,天然可当 FIFO 用:超限时淘汰最早标记的 id
const readIds = reactive(new Set<number>(loadInitial()));

function persist(): void {
  try {
    safeStorage?.setItem(STORAGE_KEY, JSON.stringify([...readIds]));
  } catch {
    // storage 不可用时已读功能静默失效
  }
}

export function isNewsRead(id: number): boolean {
  return readIds.has(id);
}

export function markNewsRead(id: number): void {
  if (readIds.has(id)) {
    return;
  }
  readIds.add(id);
  while (readIds.size > MAX_TRACKED) {
    const oldest = readIds.values().next().value;
    if (oldest === undefined) {
      break;
    }
    readIds.delete(oldest);
  }
  persist();
}

export function useReadNewsIds(): ReadonlySet<number> {
  return readIds;
}

export function resetReadNewsForTest(): void {
  readIds.clear();
  persist();
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npm run test -- --run src/utils/readNews.test.ts`
Expected: PASS

- [ ] **Step 5: 写失败测试（newsFolding）**

创建 `frontend/src/utils/newsFolding.test.ts`：

```typescript
import { describe, expect, it } from 'vitest';

import type { EditorialStoryEntry } from './newsEditorial';
import { partitionFoldableStream } from './newsFolding';

function makeEntries(count: number): EditorialStoryEntry[] {
  return Array.from({ length: count }, (_, index) => ({
    item: {
      id: index + 1,
      title: `t${index}`,
      source_name: 's',
      market: 'us',
      fetched_at: '2026-07-15T00:00:00Z',
    } as EditorialStoryEntry['item'],
    detail: null,
    score: count - index,
  }));
}

describe('partitionFoldableStream', () => {
  it('少于最小可见数时不折叠', () => {
    const { visible, folded } = partitionFoldableStream(makeEntries(10));
    expect(visible).toHaveLength(10);
    expect(folded).toHaveLength(0);
  });

  it('尾部低于 P70 且折叠段足够大时折叠', () => {
    const { visible, folded } = partitionFoldableStream(makeEntries(40));
    expect(visible).toHaveLength(28);
    expect(folded).toHaveLength(12);
    expect(folded[0]?.item.id).toBe(29);
  });

  it('折叠段太小(不足 3 条)时不折叠', () => {
    // 12 条:cutoff=max(10, ceil(12*0.7)=9)=10,尾部仅 2 条 < 3,不折叠
    const { visible, folded } = partitionFoldableStream(makeEntries(12));
    expect(visible).toHaveLength(12);
    expect(folded).toHaveLength(0);
  });

  it('至少保留前 10 条可见', () => {
    const { visible } = partitionFoldableStream(makeEntries(14));
    expect(visible.length).toBeGreaterThanOrEqual(10);
  });
});
```

- [ ] **Step 6: 跑测试确认失败**

Run: `cd frontend && npm run test -- --run src/utils/newsFolding.test.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 7: 实现 newsFolding.ts**

创建 `frontend/src/utils/newsFolding.ts`：

```typescript
import type { EditorialStoryEntry } from './newsEditorial';

export interface FoldedStream {
  visible: EditorialStoryEntry[];
  folded: EditorialStoryEntry[];
}

const MIN_VISIBLE = 10;
const FOLD_PERCENTILE = 0.7;
const MIN_FOLD_SIZE = 3;

/**
 * 把已按编辑分降序的流切成「可见段 + 折叠段」。
 * 折叠段 = 排名 P70 之后的尾部;不足 MIN_FOLD_SIZE 条就不折叠(避免「已折叠 1 条」)。
 */
export function partitionFoldableStream(entries: EditorialStoryEntry[]): FoldedStream {
  const cutoff = Math.max(MIN_VISIBLE, Math.ceil(entries.length * FOLD_PERCENTILE));
  if (entries.length - cutoff < MIN_FOLD_SIZE) {
    return { visible: entries, folded: [] };
  }
  return { visible: entries.slice(0, cutoff), folded: entries.slice(cutoff) };
}
```

- [ ] **Step 8: 跑测试确认通过**

Run: `cd frontend && npm run test -- --run src/utils/newsFolding.test.ts`
Expected: PASS（40 条 → cutoff=28 可见、12 折叠；12 条 → cutoff=10、尾部 2 条不足 MIN_FOLD_SIZE 不折叠；14 条 → cutoff=10、折叠 4 条且可见 ≥10）

- [ ] **Step 9: Commit**

```bash
git add frontend/src/utils/readNews.ts frontend/src/utils/readNews.test.ts frontend/src/utils/newsFolding.ts frontend/src/utils/newsFolding.test.ts
git commit -m "feat(frontend): 已读状态存储与低分折叠工具"
```

---

### Task 4: useFeedKeyboard 键盘流 composable

**Files:**
- Create: `frontend/src/composables/useFeedKeyboard.ts`
- Create: `frontend/src/composables/useFeedKeyboard.test.ts`

**Interfaces:**
- Produces:

```typescript
interface FeedKeyboardOptions {
  ids: () => number[];                       // 当前可见顺序的新闻 id
  isDrawerOpen: () => boolean;
  openDrawer: (id: number) => void;
  closeDrawer: () => void;
  onSelect?: (id: number, index: number) => void; // 滚动跟随用
}
function useFeedKeyboard(options: FeedKeyboardOptions): {
  selectedId: Ref<number | null>;
  handleKeydown: (event: KeyboardEvent) => void;  // 已自动挂到 window keydown
}
```

- 行为约定：`j`/`k` 上下移动选中（抽屉开着时直接切换抽屉内容）；`Enter` 打开当前选中；`Esc` 关抽屉；输入控件聚焦或带修饰键时全部忽略。T9 消费。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/composables/useFeedKeyboard.test.ts`：

```typescript
import { mount } from '@vue/test-utils';
import { defineComponent, h } from 'vue';
import { describe, expect, it, vi } from 'vitest';

import { useFeedKeyboard } from './useFeedKeyboard';

function setup(options: { drawerOpen?: boolean } = {}) {
  const openDrawer = vi.fn();
  const closeDrawer = vi.fn();
  const onSelect = vi.fn();
  let exposed!: ReturnType<typeof useFeedKeyboard>;
  const wrapper = mount(
    defineComponent({
      setup() {
        exposed = useFeedKeyboard({
          ids: () => [11, 22, 33],
          isDrawerOpen: () => options.drawerOpen ?? false,
          openDrawer,
          closeDrawer,
          onSelect,
        });
        return () => h('div');
      },
    }),
  );
  return { wrapper, openDrawer, closeDrawer, onSelect, keyboard: () => exposed };
}

function press(key: string, target?: EventTarget) {
  const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
  if (target) {
    Object.defineProperty(event, 'target', { value: target });
  }
  window.dispatchEvent(event);
  return event;
}

describe('useFeedKeyboard', () => {
  it('j/k 顺序移动选中并回调 onSelect', () => {
    const { keyboard, onSelect } = setup();
    press('j');
    expect(keyboard().selectedId.value).toBe(11);
    press('j');
    expect(keyboard().selectedId.value).toBe(22);
    press('k');
    expect(keyboard().selectedId.value).toBe(11);
    expect(onSelect).toHaveBeenCalledWith(11, 0);
  });

  it('Enter 打开当前选中', () => {
    const { keyboard, openDrawer } = setup();
    press('j');
    press('Enter');
    expect(openDrawer).toHaveBeenCalledWith(11);
    expect(keyboard().selectedId.value).toBe(11);
  });

  it('抽屉打开时 j 直接切换抽屉内容, Esc 关闭', () => {
    const { openDrawer, closeDrawer } = setup({ drawerOpen: true });
    press('j');
    expect(openDrawer).toHaveBeenCalledWith(11);
    press('Escape');
    expect(closeDrawer).toHaveBeenCalled();
  });

  it('输入框聚焦时忽略快捷键', () => {
    const { keyboard } = setup();
    const input = document.createElement('input');
    press('j', input);
    expect(keyboard().selectedId.value).toBeNull();
  });

  it('卸载后不再监听', () => {
    const { wrapper, keyboard } = setup();
    wrapper.unmount();
    press('j');
    expect(keyboard().selectedId.value).toBeNull();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npm run test -- --run src/composables/useFeedKeyboard.test.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 composable**

创建 `frontend/src/composables/useFeedKeyboard.ts`：

```typescript
import { onBeforeUnmount, onMounted, ref } from 'vue';
import type { Ref } from 'vue';

export interface FeedKeyboardOptions {
  ids: () => number[];
  isDrawerOpen: () => boolean;
  openDrawer: (id: number) => void;
  closeDrawer: () => void;
  onSelect?: (id: number, index: number) => void;
}

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return EDITABLE_TAGS.has(target.tagName) || target.isContentEditable;
}

export function useFeedKeyboard(options: FeedKeyboardOptions): {
  selectedId: Ref<number | null>;
  handleKeydown: (event: KeyboardEvent) => void;
} {
  const selectedId = ref<number | null>(null);

  function move(step: 1 | -1): void {
    const ids = options.ids();
    if (!ids.length) {
      return;
    }
    const currentIndex = selectedId.value === null ? -1 : ids.indexOf(selectedId.value);
    const nextIndex =
      currentIndex === -1
        ? step === 1
          ? 0
          : ids.length - 1
        : Math.min(ids.length - 1, Math.max(0, currentIndex + step));
    const nextId = ids[nextIndex];
    if (nextId === undefined) {
      return;
    }
    selectedId.value = nextId;
    if (options.isDrawerOpen()) {
      options.openDrawer(nextId);
    }
    options.onSelect?.(nextId, nextIndex);
  }

  function handleKeydown(event: KeyboardEvent): void {
    if (event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    if (isEditableTarget(event.target)) {
      return;
    }
    if (event.key === 'j') {
      event.preventDefault();
      move(1);
      return;
    }
    if (event.key === 'k') {
      event.preventDefault();
      move(-1);
      return;
    }
    if (event.key === 'Enter') {
      if (selectedId.value !== null && !options.isDrawerOpen()) {
        event.preventDefault();
        options.openDrawer(selectedId.value);
      }
      return;
    }
    if (event.key === 'Escape' && options.isDrawerOpen()) {
      event.preventDefault();
      options.closeDrawer();
    }
  }

  onMounted(() => window.addEventListener('keydown', handleKeydown));
  onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown));

  return { selectedId, handleKeydown };
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npm run test -- --run src/composables/useFeedKeyboard.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useFeedKeyboard.ts frontend/src/composables/useFeedKeyboard.test.ts
git commit -m "feat(frontend): 新闻流键盘导航 composable(j/k/Enter/Esc)"
```

---

### Task 5: EventCapsuleStrip + TopicChipsRow 紧凑条组件

**Files:**
- Create: `frontend/src/components/news/EventCapsuleStrip.vue`
- Create: `frontend/src/components/news/EventCapsuleStrip.test.ts`
- Create: `frontend/src/components/news/TopicChipsRow.vue`
- Create: `frontend/src/components/news/TopicChipsRow.test.ts`

**Interfaces:**
- Produces:
  - `EventCapsuleStrip`：props `{ events: NewsFeedEventCard[] }`，emits `'open-event': [eventKey: string]`，根节点 `data-role="event-capsule-strip"`，单枚胶囊 `data-role="event-capsule"`。
  - `TopicChipsRow`：props `{ topics: NewsFeedTopic[] }`，emits `'open-topic': [id: number]`，根节点 `data-role="topic-chips-row"`，单枚 chip `data-role="topic-chip"`。
- Consumes: `NewsFeedEventCard`/`NewsFeedTopic`（`src/types/api.ts`）、`sentimentText`（`src/utils/format.ts`）。T9 消费。
- 设计注记：主题溢出用横向滚动（对 spec「▸更多弹出层」的有意简化，YAGNI）。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/components/news/EventCapsuleStrip.test.ts`：

```typescript
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { NewsFeedEventCard } from '../../types/api';
import EventCapsuleStrip from './EventCapsuleStrip.vue';

function makeEvent(overrides: Partial<NewsFeedEventCard> = {}): NewsFeedEventCard {
  return {
    event_key: 'topic-1',
    event_title: '英伟达上调指引',
    event_type: 'earnings',
    market: 'us',
    sentiment_label: 'positive',
    importance_score: 0.8,
    primary_symbol: 'NVDA',
    related_symbols: ['NVDA'],
    watchlist_hits: ['NVDA 英伟达'],
    source_count: 3,
    news_count: 5,
    news_items: [],
    ...overrides,
  };
}

describe('EventCapsuleStrip', () => {
  it('渲染事件胶囊并透传点击', async () => {
    const wrapper = mount(EventCapsuleStrip, { props: { events: [makeEvent()] } });
    const capsule = wrapper.get('[data-role="event-capsule"]');
    expect(capsule.text()).toContain('英伟达上调指引');
    expect(capsule.text()).toContain('US');
    await capsule.trigger('click');
    expect(wrapper.emitted('open-event')).toEqual([['topic-1']]);
  });

  it('空列表显示占位文案', () => {
    const wrapper = mount(EventCapsuleStrip, { props: { events: [] } });
    expect(wrapper.get('[data-role="event-capsule-strip"]').text()).toContain('暂无聚合事件');
  });

  it('命中持仓时显示计数徽标', () => {
    const wrapper = mount(EventCapsuleStrip, { props: { events: [makeEvent()] } });
    expect(wrapper.text()).toContain('持仓 1');
  });
});
```

创建 `frontend/src/components/news/TopicChipsRow.test.ts`：

```typescript
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { NewsFeedTopic } from '../../types/api';
import TopicChipsRow from './TopicChipsRow.vue';

function makeTopic(overrides: Partial<NewsFeedTopic> = {}): NewsFeedTopic {
  return {
    id: 7,
    topic_title: 'AI 芯片',
    keywords: ['ai'],
    market: 'us',
    sentiment_label: 'positive',
    importance_score: 0.6,
    news_count: 12,
    last_seen_at: '2026-07-15T00:00:00Z',
    related_symbols: [],
    ...overrides,
  };
}

describe('TopicChipsRow', () => {
  it('渲染主题 chip 并透传点击', async () => {
    const wrapper = mount(TopicChipsRow, { props: { topics: [makeTopic()] } });
    const chip = wrapper.get('[data-role="topic-chip"]');
    expect(chip.text()).toContain('AI 芯片');
    expect(chip.text()).toContain('(12)');
    await chip.trigger('click');
    expect(wrapper.emitted('open-topic')).toEqual([[7]]);
  });

  it('空列表显示占位文案', () => {
    const wrapper = mount(TopicChipsRow, { props: { topics: [] } });
    expect(wrapper.get('[data-role="topic-chips-row"]').text()).toContain('暂无主题');
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npm run test -- --run src/components/news/EventCapsuleStrip.test.ts src/components/news/TopicChipsRow.test.ts`
Expected: FAIL（组件不存在）

- [ ] **Step 3: 实现 EventCapsuleStrip.vue**

```vue
<script setup lang="ts">
import { sentimentText } from '../../utils/format';
import type { NewsFeedEventCard } from '../../types/api';

defineProps<{ events: NewsFeedEventCard[] }>();

const emit = defineEmits<{ 'open-event': [eventKey: string] }>();
</script>

<template>
  <div class="capsule-strip" data-role="event-capsule-strip">
    <span class="capsule-strip__label">事件雷达</span>
    <p v-if="!events.length" class="capsule-strip__empty">暂无聚合事件</p>
    <div v-else class="capsule-strip__scroller">
      <button
        v-for="event in events"
        :key="event.event_key"
        type="button"
        class="capsule"
        data-role="event-capsule"
        :aria-label="`查看事件 ${event.event_title}`"
        @click="emit('open-event', event.event_key)"
      >
        <span class="capsule__type">{{ event.event_type }}</span>
        <span
          class="capsule__dot"
          :class="event.sentiment_label"
          :title="sentimentText(event.sentiment_label)"
        ></span>
        <span class="capsule__market">{{ event.market.toUpperCase() }}</span>
        <span class="capsule__title">{{ event.event_title }}</span>
        <span v-if="(event.watchlist_hits ?? []).length" class="capsule__hits">
          持仓 {{ (event.watchlist_hits ?? []).length }}
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.capsule-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.capsule-strip__label {
  flex: none;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.capsule-strip__empty {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.capsule-strip__scroller {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: thin;
  padding-bottom: 2px;
  min-width: 0;
}

.capsule {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 340px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--panel-strong);
  color: var(--text-soft);
  font-size: 12px;
  line-height: 1.2;
  cursor: pointer;
  transition: border-color 140ms ease, color 140ms ease;
}

.capsule:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.capsule__type {
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.capsule__dot {
  flex: none;
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--accent);
}

.capsule__dot.positive {
  background: var(--positive);
}

.capsule__dot.negative {
  background: var(--negative);
}

.capsule__market {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.08em;
}

.capsule__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text);
}

.capsule__hits {
  flex: none;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 10.5px;
}
</style>
```

- [ ] **Step 4: 实现 TopicChipsRow.vue**

```vue
<script setup lang="ts">
import type { NewsFeedTopic } from '../../types/api';

defineProps<{ topics: NewsFeedTopic[] }>();

const emit = defineEmits<{ 'open-topic': [id: number] }>();
</script>

<template>
  <div class="topic-chips" data-role="topic-chips-row">
    <span class="topic-chips__label">主题</span>
    <p v-if="!topics.length" class="topic-chips__empty">暂无主题</p>
    <div v-else class="topic-chips__scroller">
      <button
        v-for="topic in topics"
        :key="topic.id"
        type="button"
        class="topic-chip"
        data-role="topic-chip"
        @click="emit('open-topic', topic.id)"
      >
        {{ topic.topic_title }}
        <span class="topic-chip__count">({{ topic.news_count }})</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.topic-chips {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.topic-chips__label {
  flex: none;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.topic-chips__empty {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.topic-chips__scroller {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: thin;
  padding-bottom: 2px;
  min-width: 0;
}

.topic-chip {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 11px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--panel-strong);
  color: var(--text-soft);
  font-size: 12px;
  line-height: 1.2;
  cursor: pointer;
  transition: border-color 140ms ease, color 140ms ease;
}

.topic-chip:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.topic-chip__count {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
}
</style>
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd frontend && npm run test -- --run src/components/news/EventCapsuleStrip.test.ts src/components/news/TopicChipsRow.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/news/EventCapsuleStrip.vue frontend/src/components/news/EventCapsuleStrip.test.ts frontend/src/components/news/TopicChipsRow.vue frontend/src/components/news/TopicChipsRow.test.ts
git commit -m "feat(frontend): 事件胶囊条与主题 chips 行组件"
```

---

### Task 6: 分类器顺路产出 takeaway（依赖 T1）

**Files:**
- Modify: `backend/app/services/news_signal_classifier.py`
- Modify: `backend/app/services/news_signal_pipeline.py`（`_apply_result`，第 186-233 行）
- Create: `backend/tests/test_takeaway_classifier.py`
- Modify: `backend/tests/test_news_signal_pipeline.py`（追加一个用例）

**Interfaces:**
- Consumes: T1 的 `NewsItem.ai_takeaway`。
- Produces: `ClassificationResult.takeaway: str | None = None`；`_apply_result` 在 `result.takeaway` 非空且 `item.ai_takeaway` 为空时写入。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_takeaway_classifier.py`：

```python
from unittest.mock import patch

from app.db.session import SessionLocal
from app.services import news_signal_classifier as classifier_module
from app.services.news_signal_classifier import ClassificationResult, NewsSignalClassifier


class _FakeProvider:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def analyze_json(self, *, prompt: str) -> object:
        assert "takeaway" in prompt
        return self._payload


def _baseline() -> ClassificationResult:
    return ClassificationResult(
        sentiment_label="neutral",
        sentiment_score=0.0,
        signal_confidence=0.4,
        keywords=["ai"],
        topic_key="ai",
        summary="s",
        classifier_type="rule",
    )


def _refine(payload: object) -> ClassificationResult:
    with SessionLocal() as session:
        classifier = NewsSignalClassifier(session)
        with (
            patch.object(classifier.config_repository, "get_active", return_value=object()),
            patch.object(classifier_module, "build_provider", return_value=_FakeProvider(payload)),
        ):
            return classifier._llm_refine(_baseline(), title="t", summary="s", body="b")


def test_classification_result_defaults_takeaway_none() -> None:
    assert _baseline().takeaway is None


def test_llm_refine_parses_and_trims_takeaway() -> None:
    result = _refine({"takeaway": "  英伟达产业链受益,偏利好。 "})
    assert result.takeaway == "英伟达产业链受益,偏利好。"


def test_llm_refine_truncates_long_takeaway() -> None:
    result = _refine({"takeaway": "长" * 300})
    assert result.takeaway is not None
    assert len(result.takeaway) == 120


def test_llm_refine_tolerates_missing_takeaway_key() -> None:
    result = _refine({"sentiment_label": "positive"})
    assert result.takeaway is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n news-caught pytest backend/tests/test_takeaway_classifier.py -q`
Expected: FAIL（`ClassificationResult` 无 `takeaway` 字段）

- [ ] **Step 3: 实现分类器改动**

`backend/app/services/news_signal_classifier.py` 三处：

(a) `ClassificationResult`（第 153-164 行）追加字段（放在 `topic_summary_hint` 之后）：

```python
    takeaway: str | None = None
```

(b) `_llm_refine` 的 prompt（第 230-237 行）改为：

```python
        prompt = "\n".join(
            [
                f"Title: {title}",
                f"Summary: {summary or ''}",
                f"Body: {body or ''}",
                "Return JSON only with keys: sentiment_label, sentiment_score, summary, keywords, topic_title_hint, takeaway.",
                "takeaway: 一句中文结论(<=60字),说明谁受影响、偏利好还是利空、原因;无法判断时返回空字符串。",
            ]
        )
```

(c) 解析段：在 `summary_text = (...)`（第 262-266 行）之后加：

```python
        takeaway_raw = payload.get("takeaway")
        takeaway_text = str(takeaway_raw).strip() if takeaway_raw else ""
        takeaway = takeaway_text[:120] if takeaway_text else None
```

并在末尾返回的 `ClassificationResult(...)`（第 267-282 行）中加入：

```python
            takeaway=takeaway,
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n news-caught pytest backend/tests/test_takeaway_classifier.py -q`
Expected: 4 passed

- [ ] **Step 5: 管线写回 + 回归测试**

`backend/app/services/news_signal_pipeline.py` 的 `_apply_result`，在 `item.signal_updated_at = _utc_now()`（第 216 行）之后加：

```python
        if result.takeaway and not item.ai_takeaway:
            item.ai_takeaway = result.takeaway
```

在 `backend/tests/test_news_signal_pipeline.py` 中追加以下完整用例（缺的 import 补进该文件 import 区即可）：

```python
def test_apply_result_writes_takeaway_without_overwrite() -> None:
    import sqlalchemy as sa

    from app.db.session import SessionLocal
    from app.models.news_item import NewsItem
    from app.models.news_signal_result import NewsSignalResult
    from app.models.topic_cluster import TopicCluster
    from app.models.topic_news_link import TopicNewsLink
    from app.services.news_signal_classifier import ClassificationResult
    from app.services.news_signal_pipeline import NewsSignalPipelineService
    from datetime import datetime, timezone

    def _result(takeaway: str) -> ClassificationResult:
        return ClassificationResult(
            sentiment_label="positive",
            sentiment_score=0.5,
            signal_confidence=0.8,
            keywords=["takeaway", "apply"],
            topic_key="takeaway-apply-topic",
            summary="s",
            classifier_type="hybrid",
            takeaway=takeaway,
        )

    with SessionLocal() as session:
        item = NewsItem(
            source_name="UnitTest",
            source_url="https://example.com/apply-tk",
            title="apply takeaway",
            canonical_url="https://example.com/apply-tk",
            url_hash="hash-apply-tk",
            market="us",
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(item)
        session.flush()
        service = NewsSignalPipelineService(session, session_factory=SessionLocal)
        try:
            service._apply_result(item, _result("首次结论"), set())
            session.commit()
            session.refresh(item)
            assert item.ai_takeaway == "首次结论"

            service._apply_result(item, _result("第二次结论"), set())
            session.commit()
            session.refresh(item)
            assert item.ai_takeaway == "首次结论"  # 已有值不覆盖
        finally:
            session.rollback()
            session.execute(sa.delete(TopicNewsLink).where(TopicNewsLink.news_id == item.id))
            session.execute(sa.delete(NewsSignalResult).where(NewsSignalResult.news_id == item.id))
            session.execute(sa.delete(TopicCluster).where(TopicCluster.topic_key == "takeaway-apply-topic"))
            session.execute(sa.delete(NewsItem).where(NewsItem.id == item.id))
            session.commit()
```

- [ ] **Step 6: 跑管线回归**

Run: `conda run -n news-caught pytest backend/tests/test_news_signal_pipeline.py backend/tests/test_takeaway_classifier.py -q`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/news_signal_classifier.py backend/app/services/news_signal_pipeline.py backend/tests/test_takeaway_classifier.py backend/tests/test_news_signal_pipeline.py
git commit -m "feat(backend): LLM 精修顺路产出一句话结论并写回 ai_takeaway"
```

---

### Task 7: takeaway 补齐服务 + Worker + feed layout 入队钩子（依赖 T1）

**Files:**
- Create: `backend/app/services/news_takeaway.py`
- Create: `backend/app/workers/takeaway_worker.py`
- Modify: `backend/app/core/config.py`（Settings 加 3 个字段）
- Modify: `backend/app/main.py`（lifespan 启停 worker）
- Modify: `backend/app/services/news_feed_layout.py`（`build` 末尾入队钩子）
- Create: `backend/tests/test_news_takeaway_service.py`

**Interfaces:**
- Consumes: T1 的 `ai_takeaway` 列/schema；`BaseWorker`（`app/workers/base_worker.py`：`worker_name`、`__init__(*, session_factory, logger=None)`、`get_interval()`、`do_cycle() -> int`、`_stop_event`）；`LLMProviderConfigRepository.get_active()`；`build_provider(config).analyze_json(prompt=...)`。
- Produces: `enqueue_takeaway_candidates(news_ids: list[int])`、`takeaway_queue`、`NewsTakeawayService.generate_for_ids(news_ids, *, batch_limit) -> list[NewsItem]`、`TakeawayWorker`。事件：每条 `news.updated`（payload = NewsItemSummary dump + `updated_fields: ["ai_takeaway"]`，SSE 会转发）+ 一条 `news.signals_processed`（触发路由缓存失效）。

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_news_takeaway_service.py`：

```python
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.db.session import SessionLocal
from app.models.news_item import NewsItem
from app.services import news_takeaway as takeaway_module
from app.services.news_takeaway import NewsTakeawayService, enqueue_takeaway_candidates, takeaway_queue
from app.workers import takeaway_worker as worker_module
from app.workers.takeaway_worker import TakeawayWorker


class _FakeProvider:
    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.calls = 0

    def analyze_json(self, *, prompt: str) -> object:
        self.calls += 1
        return self._payload


def _make_item(session, *, suffix: str, takeaway: str | None = None) -> NewsItem:
    item = NewsItem(
        source_name="UnitTest",
        source_url=f"https://example.com/tk-{suffix}",
        title=f"takeaway {suffix}",
        canonical_url=f"https://example.com/tk-{suffix}",
        url_hash=f"hash-tk-{suffix}",
        market="us",
        fetched_at=datetime.now(timezone.utc),
        ai_takeaway=takeaway,
    )
    session.add(item)
    session.flush()
    return item


def _cleanup(session, ids: list[int]) -> None:
    for news_id in ids:
        row = session.get(NewsItem, news_id)
        if row is not None:
            session.delete(row)
    session.commit()


def test_generate_skips_items_with_existing_takeaway() -> None:
    provider = _FakeProvider({"takeaway": "一句话结论"})
    with SessionLocal() as session:
        fresh = _make_item(session, suffix="fresh")
        done = _make_item(session, suffix="done", takeaway="已有结论")
        session.commit()
        ids = [fresh.id, done.id]
        try:
            service = NewsTakeawayService(session)
            with (
                patch.object(service.config_repository, "get_active", return_value=object()),
                patch.object(takeaway_module, "build_provider", return_value=provider),
            ):
                updated = service.generate_for_ids(ids, batch_limit=10)
            session.commit()
            assert [item.id for item in updated] == [fresh.id]
            assert provider.calls == 1
            session.refresh(fresh)
            assert fresh.ai_takeaway == "一句话结论"
        finally:
            _cleanup(session, ids)


def test_generate_respects_batch_limit_and_tolerates_failure() -> None:
    class _FailingProvider:
        def analyze_json(self, *, prompt: str) -> object:
            raise RuntimeError("llm down")

    with SessionLocal() as session:
        a = _make_item(session, suffix="a")
        b = _make_item(session, suffix="b")
        session.commit()
        ids = [a.id, b.id]
        try:
            service = NewsTakeawayService(session)
            with (
                patch.object(service.config_repository, "get_active", return_value=object()),
                patch.object(takeaway_module, "build_provider", return_value=_FailingProvider()),
            ):
                updated = service.generate_for_ids(ids, batch_limit=1)
            assert updated == []
        finally:
            _cleanup(session, ids)


def test_generate_without_active_config_is_noop() -> None:
    with SessionLocal() as session:
        item = _make_item(session, suffix="noconf")
        session.commit()
        try:
            service = NewsTakeawayService(session)
            with patch.object(service.config_repository, "get_active", return_value=None):
                assert service.generate_for_ids([item.id], batch_limit=5) == []
        finally:
            _cleanup(session, [item.id])


def test_worker_drains_queue_when_ai_disabled() -> None:
    enqueue_takeaway_candidates([1, 2, 3])
    worker = TakeawayWorker(session_factory=SessionLocal)
    settings = SimpleNamespace(
        ai_enabled=False, takeaway_batch_limit=12, takeaway_daily_limit=300, takeaway_poll_interval_seconds=5.0
    )
    with patch.object(worker_module, "get_settings", return_value=settings):
        assert worker.do_cycle() == 0
    assert takeaway_queue.empty()


def test_worker_generates_and_publishes() -> None:
    provider = _FakeProvider({"takeaway": "批量结论"})
    with SessionLocal() as session:
        item = _make_item(session, suffix="worker")
        session.commit()
        item_id = item.id
    published: list[tuple[str, dict]] = []
    try:
        enqueue_takeaway_candidates([item_id])
        worker = TakeawayWorker(session_factory=SessionLocal)
        settings = SimpleNamespace(
            ai_enabled=True, takeaway_batch_limit=12, takeaway_daily_limit=300, takeaway_poll_interval_seconds=5.0
        )
        fake_bus = SimpleNamespace(publish=lambda name, payload: published.append((name, payload)))
        with (
            patch.object(worker_module, "get_settings", return_value=settings),
            patch.object(worker_module, "get_event_bus", return_value=fake_bus),
            patch.object(takeaway_module, "build_provider", return_value=provider),
            patch.object(takeaway_module.LLMProviderConfigRepository, "get_active", return_value=object()),
        ):
            processed = worker.do_cycle()
        assert processed == 1
        event_names = [name for name, _ in published]
        assert "news.updated" in event_names
        assert "news.signals_processed" in event_names
        updated_payload = next(payload for name, payload in published if name == "news.updated")
        assert updated_payload["updated_fields"] == ["ai_takeaway"]
        with SessionLocal() as session:
            assert session.get(NewsItem, item_id).ai_takeaway == "批量结论"
    finally:
        with SessionLocal() as session:
            _cleanup(session, [item_id])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n news-caught pytest backend/tests/test_news_takeaway_service.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: Settings 加配置**

`backend/app/core/config.py` 在 `llm_timeout_seconds`（第 26 行）之后加：

```python
    takeaway_batch_limit: int = 12
    takeaway_daily_limit: int = 300
    takeaway_poll_interval_seconds: float = 5.0
```

- [ ] **Step 4: 实现补齐服务**

创建 `backend/app/services/news_takeaway.py`：

```python
"""高编辑分新闻的「一句话结论」补齐服务。

feed layout 构建时把缺 takeaway 的高分新闻 id 入队(enqueue_takeaway_candidates),
TakeawayWorker 后台批量调 LLM 生成并写回 news_item.ai_takeaway;一条新闻只生成一次。
"""
from __future__ import annotations

import logging
import queue

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_item import NewsItem
from app.repositories.llm_provider_config_repository import LLMProviderConfigRepository
from app.services.llm_providers import build_provider

logger = logging.getLogger(__name__)

# 全局内存补齐队列(与 queue_worker.analysis_queue 同模式)
takeaway_queue: queue.Queue[list[int]] = queue.Queue()

TAKEAWAY_MAX_LEN = 120


def enqueue_takeaway_candidates(news_ids: list[int]) -> None:
    if news_ids:
        takeaway_queue.put(news_ids)


class NewsTakeawayService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.config_repository = LLMProviderConfigRepository(session)

    def generate_for_ids(self, news_ids: list[int], *, batch_limit: int) -> list[NewsItem]:
        """为缺 takeaway 的新闻生成一句话结论,返回成功写回的条目(不 commit,由调用方决定)。"""
        if not news_ids or batch_limit <= 0:
            return []
        config = self.config_repository.get_active()
        if config is None:
            return []

        stmt = (
            select(NewsItem)
            .where(NewsItem.id.in_(news_ids), NewsItem.ai_takeaway.is_(None))
            .limit(batch_limit)
        )
        items = list(self.session.scalars(stmt))
        updated: list[NewsItem] = []
        for item in items:
            prompt = "\n".join(
                [
                    f"Title: {item.title}",
                    f"Summary: {item.summary or ''}",
                    f"Market: {item.market}",
                    "You write one-line conclusions for stock-market news readers.",
                    "Return JSON only with keys: takeaway.",
                    "takeaway: 一句中文结论(<=60字),说明谁受影响、偏利好还是利空、原因;无法判断时返回空字符串。",
                ]
            )
            try:
                payload = build_provider(config).analyze_json(prompt=prompt)
            except Exception as exc:
                logger.warning("takeaway generation failed for news %s: %s", item.id, exc)
                continue
            takeaway = str(payload.get("takeaway") or "").strip() if isinstance(payload, dict) else ""
            if not takeaway:
                continue
            item.ai_takeaway = takeaway[:TAKEAWAY_MAX_LEN]
            updated.append(item)
        return updated
```

- [ ] **Step 5: 实现 Worker**

创建 `backend/app/workers/takeaway_worker.py`：

```python
"""Takeaway 补齐 Worker:消化 takeaway_queue,受批量/日上限约束地生成一句话结论。"""
from __future__ import annotations

import queue
from collections.abc import Callable
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.news import NewsItemSummary
from app.services.event_bus import get_event_bus
from app.services.news_takeaway import NewsTakeawayService, takeaway_queue
from app.workers.base_worker import BaseWorker


class TakeawayWorker(BaseWorker):
    worker_name = "takeaway_worker"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        poll_interval_seconds: float | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory)
        self.poll_interval_seconds = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else get_settings().takeaway_poll_interval_seconds
        )
        # 日配额为进程内计数,重启即重置——单机自用场景下的简单护栏
        self._generated_on: date | None = None
        self._generated_count = 0

    def get_interval(self) -> float:
        return self.poll_interval_seconds

    def _remaining_daily_quota(self) -> int:
        today = date.today()
        if self._generated_on != today:
            self._generated_on = today
            self._generated_count = 0
        return max(0, get_settings().takeaway_daily_limit - self._generated_count)

    def _drain_queue(self) -> set[int]:
        batch_ids: set[int] = set()
        while not self._stop_event.is_set():
            try:
                batch_ids.update(takeaway_queue.get_nowait())
                takeaway_queue.task_done()
            except queue.Empty:
                break
        return batch_ids

    def do_cycle(self) -> int:
        settings = get_settings()
        if not settings.ai_enabled:
            # AI 关闭时抽干队列丢弃,避免堆积
            self._drain_queue()
            return 0

        batch_ids = self._drain_queue()
        if not batch_ids:
            return 0

        quota = self._remaining_daily_quota()
        if quota <= 0:
            self.logger.warning("takeaway daily limit reached, dropping %s candidates", len(batch_ids))
            return 0

        batch_limit = min(settings.takeaway_batch_limit, quota)
        event_bus = get_event_bus()
        with self.session_factory() as session:
            service = NewsTakeawayService(session)
            updated = service.generate_for_ids(sorted(batch_ids), batch_limit=batch_limit)
            payloads = [
                {
                    **NewsItemSummary.model_validate(item, from_attributes=True).model_dump(mode="json"),
                    "updated_fields": ["ai_takeaway"],
                }
                for item in updated
            ]
            updated_ids = [item.id for item in updated]
            session.commit()

        self._generated_count += len(updated_ids)
        for payload in payloads:
            event_bus.publish("news.updated", payload)
        if updated_ids:
            event_bus.publish(
                "news.signals_processed",
                {"news_ids": updated_ids, "processed_count": len(updated_ids)},
            )
        return len(updated_ids)
```

- [ ] **Step 6: feed layout 入队钩子**

`backend/app/services/news_feed_layout.py`：

(a) imports 区加（若未有）：

```python
from app.core.config import get_settings
from app.services.news_takeaway import enqueue_takeaway_candidates
```

(b) `NewsFeedLayoutService.build`（第 588-616 行）中，`return NewsFeedLayoutView(...)` 之前加一行：

```python
        self._enqueue_takeaway_candidates(event_cards[:limit_events], scored_stream)
```

(c) 类内新增静态方法：

```python
    @staticmethod
    def _enqueue_takeaway_candidates(
        event_cards: list[NewsFeedEventCardView],
        scored_stream: list[NewsItemSummary],
    ) -> None:
        """把缺 takeaway 的高分条目送入补齐队列(非阻塞,失败不影响主链路)。"""
        try:
            if not get_settings().ai_enabled:
                return
            top_n = max(8, int(len(scored_stream) * 0.2))
            candidate_ids = {item.id for item in scored_stream[:top_n] if item.ai_takeaway is None}
            for card in event_cards:
                candidate_ids.update(item.id for item in card.news_items if item.ai_takeaway is None)
            if candidate_ids:
                enqueue_takeaway_candidates(sorted(candidate_ids))
        except Exception:  # noqa: BLE001
            logger.warning("takeaway candidate enqueue failed", exc_info=True)
```

（该文件顶部已有 `logger`；若无则 `logger = logging.getLogger(__name__)`。）

- [ ] **Step 7: main.py 启停**

`backend/app/main.py`：

(a) imports 加：`from app.workers.takeaway_worker import TakeawayWorker`（与 BackgroundQueueWorker import 相邻）。

(b) lifespan 中 `queue_worker.start()`（第 114 行）之后加：

```python
    takeaway_worker = TakeawayWorker(session_factory=SessionLocal)
    takeaway_worker.start()
```

(c) shutdown 段 `queue_worker.stop()`（第 171 行）之后加：

```python
    takeaway_worker.stop()
```

- [ ] **Step 8: 跑测试确认通过 + 回归**

Run: `conda run -n news-caught pytest backend/tests/test_news_takeaway_service.py backend/tests/test_news_feed_layout.py -q`
Expected: 全部 PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/news_takeaway.py backend/app/workers/takeaway_worker.py backend/app/core/config.py backend/app/main.py backend/app/services/news_feed_layout.py backend/tests/test_news_takeaway_service.py
git commit -m "feat(backend): takeaway 补齐服务与后台 worker(批量/日上限护栏)"
```

---

### Task 8: NewsCard 改造 — 色条 / AI 结论行 / 已读与选中态（依赖 T1、T3）

**Files:**
- Modify: `frontend/src/components/news/NewsCard.vue`
- Modify: `frontend/src/components/news/NewsCard.test.ts`

**Interfaces:**
- Consumes: T1 后的 `NewsItem.ai_takeaway?: string | null`。
- Produces: props 新增 `read?: boolean`（默认 false）、`selected?: boolean`（默认 false）；根节点新增 `:data-news-id="entry.item.id"`；新 data-role：`news-card-takeaway`、`news-card-unread`。T9 消费。

- [ ] **Step 1: 写失败测试**

在 `frontend/src/components/news/NewsCard.test.ts` 追加用例（沿用现有 `makeEntry()` helper，若其 item 未含 `ai_takeaway` 字段则给 overrides 支持）：

```typescript
  it('有 ai_takeaway 时显示结论行', () => {
    const entry = makeEntry();
    entry.item = { ...entry.item, ai_takeaway: '数据中心需求超预期,利好产业链' };
    const wrapper = mount(NewsCard, { props: { entry, variant: 'stream-compact' } });
    expect(wrapper.get('[data-role="news-card-takeaway"]').text()).toContain('数据中心需求超预期');
  });

  it('无 ai_takeaway 时回退显示原文摘要且无结论行', () => {
    const wrapper = mount(NewsCard, { props: { entry: makeEntry(), variant: 'stream-compact' } });
    expect(wrapper.find('[data-role="news-card-takeaway"]').exists()).toBe(false);
    expect(wrapper.find('.summary').exists()).toBe(true);
  });

  it('read 时加淡化 class,未读时显示圆点', () => {
    const read = mount(NewsCard, { props: { entry: makeEntry(), read: true } });
    expect(read.classes()).toContain('news-card--read');
    expect(read.find('[data-role="news-card-unread"]').exists()).toBe(false);
    const unread = mount(NewsCard, { props: { entry: makeEntry() } });
    expect(unread.find('[data-role="news-card-unread"]').exists()).toBe(true);
  });

  it('selected 时加选中 class,并带 data-news-id', () => {
    const wrapper = mount(NewsCard, { props: { entry: makeEntry(), selected: true } });
    expect(wrapper.classes()).toContain('news-card--selected');
    expect(wrapper.attributes('data-news-id')).toBeDefined();
  });

  it('情绪与强度映射为色条 class', () => {
    const entry = makeEntry();
    entry.item = { ...entry.item, sentiment_label: 'negative' };
    entry.score = 1.2;
    const wrapper = mount(NewsCard, { props: { entry } });
    expect(wrapper.classes()).toContain('news-card--tone-negative');
    expect(wrapper.classes()).toContain('news-card--tier-strong');
  });
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npm run test -- --run src/components/news/NewsCard.test.ts`
Expected: 新增用例 FAIL

- [ ] **Step 3: 实现 NewsCard 改动**

`frontend/src/components/news/NewsCard.vue`：

(a) props（第 9-17 行）改为：

```typescript
const props = withDefaults(
  defineProps<{
    entry: EditorialStoryEntry;
    variant?: 'supporting' | 'stream' | 'stream-compact';
    read?: boolean;
    selected?: boolean;
  }>(),
  {
    variant: 'stream',
    read: false,
    selected: false,
  },
);
```

(b) script 增加 computed（`topicLabel` 之后）：

```typescript
const takeaway = computed(() => {
  const value = (props.entry.detail ?? props.entry.item).ai_takeaway;
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
});

// 编辑分 → 色条强度三档(阈值对齐前端 getEditorialScore 的 0~1.4 区间)
const intensityTier = computed(() => {
  if (props.entry.score >= 0.9) {
    return 'strong';
  }
  if (props.entry.score >= 0.55) {
    return 'medium';
  }
  return 'soft';
});

const sentimentTone = computed(() => {
  const label = props.entry.item.sentiment_label;
  return label === 'positive' || label === 'negative' ? label : 'neutral';
});
```

(c) template 根节点改为：

```html
  <article
    class="news-card"
    :class="[
      `news-card--${variant}`,
      `news-card--tone-${sentimentTone}`,
      `news-card--tier-${intensityTier}`,
      { 'news-card--read': read, 'news-card--selected': selected },
    ]"
    :data-news-id="entry.item.id"
    data-role="news-card-shell"
    @click="emit('open', entry.item.id)"
  >
```

(d) `card-head` 末尾（`.source` span 之后）加：

```html
      <span v-if="!read" class="unread-dot" data-role="news-card-unread"></span>
```

(e) 标题下的内容区（第 39-40 行）改为：

```html
        <h3 data-role="news-card-title">{{ entry.item.title }}</h3>
        <p v-if="takeaway" class="takeaway" data-role="news-card-takeaway">→ {{ takeaway }}</p>
        <p v-if="!takeaway || variant !== 'stream-compact'" class="summary">{{ summary }}</p>
```

(f) style 追加（`.news-card` 规则后）：

```css
.news-card {
  position: relative;
}

.news-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 999px;
  background: var(--accent);
  opacity: 0.3;
}

.news-card--tone-positive::before {
  background: var(--positive);
}

.news-card--tone-negative::before {
  background: var(--negative);
}

.news-card--tier-strong::before {
  opacity: 0.95;
}

.news-card--tier-medium::before {
  opacity: 0.6;
}

.news-card--tier-soft::before {
  opacity: 0.3;
}

.news-card--read {
  opacity: 0.55;
}

.news-card--read:hover {
  opacity: 0.85;
}

.news-card--selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent-soft);
}

.unread-dot {
  margin-left: auto;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--accent);
  box-shadow: 0 0 6px var(--accent-soft);
}

.takeaway {
  margin: 0;
  color: var(--accent);
  font-size: 13.5px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  -webkit-line-clamp: 2;
}

.news-card--stream-compact .takeaway {
  font-size: 13px;
  line-height: 1.45;
}
```

注意 `.news-card` 已有规则不要重复声明——把 `position: relative;` 并进现有 `.news-card` 块即可。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npm run test -- --run src/components/news/NewsCard.test.ts`
Expected: 全部 PASS（含既有用例）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/news/NewsCard.vue frontend/src/components/news/NewsCard.test.ts
git commit -m "feat(frontend): 新闻卡片加情绪色条/AI结论行/已读与选中态"
```

---

### Task 9: NewsFeedView 集成（依赖 T1-T8，串行执行）

**Files:**
- Modify: `frontend/src/views/NewsFeedView.vue`
- Modify: `frontend/src/components/news/NewsVirtualList.vue`
- Modify: `frontend/src/components/news/NewsVirtualList.test.ts`
- Modify: `frontend/src/components/news/NewsDetailDrawer.vue`（加「完整页打开」入口）
- Modify: `frontend/src/views/NewsFeedView.test.ts`
- Verify: `frontend/src/smoke/app-navigation.test.ts`（锚点 'Latest Events' 不变，应保持绿；若断言涉及被删的 data-role 才允许改）

**Interfaces:**
- Consumes: T3 `partitionFoldableStream`/`markNewsRead`/`useReadNewsIds`、T4 `useFeedKeyboard`、T5 两个紧凑条组件、T8 NewsCard 新 props、`NewsDetailDrawer`（props `newsId/visible/filteredNewsIds`，emits `close/changeNews`）。
- Produces: 新 data-role：`feed-compact-header`、`news-fold-toggle`、`feed-kbd-hint`。移除 data-role：`event-radar-shell`、`topic-watch-shell`（`news-stream-shell` 保留）。点卡片不再 router.push 到 news-detail。

- [ ] **Step 1: NewsVirtualList 扩展（先改子组件）**

`frontend/src/components/news/NewsVirtualList.vue`：

(a) props 改为：

```typescript
const props = defineProps<{
  entries: EditorialStoryEntry[];
  selectedId?: number | null;
  readIds?: ReadonlySet<number>;
}>();
```

(b) NewsCard 渲染处透传：

```html
        <NewsCard
          :entry="vis.item"
          variant="stream-compact"
          :selected="vis.item.item.id === selectedId"
          :read="readIds?.has(vis.item.item.id) ?? false"
          @open="emit('open', $event)"
        />
```

(c) script 末尾加（`containerRef` 是既有的滚动容器 ref）：

```typescript
function scrollToIndex(index: number): void {
  if (!containerRef.value) {
    return;
  }
  containerRef.value.scrollTop = Math.max(0, index * ROW_HEIGHT - containerRef.value.clientHeight / 2);
}

defineExpose({ scrollToIndex });
```

在 `NewsVirtualList.test.ts` 追加：传 `selectedId`/`readIds` 后对应 NewsCard 收到 `selected`/`read` props 的断言（用 `findComponent(NewsCard).props()`）。

- [ ] **Step 2: NewsDetailDrawer 加完整页入口**

`frontend/src/components/news/NewsDetailDrawer.vue` 头部操作区（上一篇/下一篇按钮同排）加：

```html
        <RouterLink
          v-if="newsId !== null"
          :to="{ name: 'news-detail', params: { id: newsId } }"
          class="text-xs text-muted hover:text-text"
          data-role="drawer-open-full"
          @click="emit('close')"
        >
          完整页 ↗
        </RouterLink>
```

script 加 `import { RouterLink } from 'vue-router';`。若 DashboardView.test 因此报缺 router，注入 stub：`global: { stubs: { RouterLink: true } }`（只允许为此调整该测试的 mount 选项）。

- [ ] **Step 3: NewsFeedView 集成改造**

`frontend/src/views/NewsFeedView.vue` script 部分：

(a) imports：删 `EventFeedCard`，加：

```typescript
import EventCapsuleStrip from '../components/news/EventCapsuleStrip.vue';
import TopicChipsRow from '../components/news/TopicChipsRow.vue';
import NewsDetailDrawer from '../components/news/NewsDetailDrawer.vue';
import { useFeedKeyboard } from '../composables/useFeedKeyboard';
import { partitionFoldableStream } from '../utils/newsFolding';
import { markNewsRead, useReadNewsIds } from '../utils/readNews';
```

(b) 在 `orderedEntries` 定义之后加状态与派生：

```typescript
const drawerVisible = ref(false);
const selectedNewsId = ref<number | null>(null);
const foldExpanded = ref(false);
const readIds = useReadNewsIds();
const virtualListRef = ref<InstanceType<typeof NewsVirtualList> | null>(null);

const foldedStream = computed(() => partitionFoldableStream(orderedEntries.value));
const displayEntries = computed(() =>
  foldExpanded.value
    ? [...foldedStream.value.visible, ...foldedStream.value.folded]
    : foldedStream.value.visible,
);
const displayIds = computed(() => displayEntries.value.map((entry) => entry.item.id));
```

原 `useVirtualScrolling` 定义整行替换为（注意需移到 `displayEntries` 之后）：

```typescript
const useVirtualScrolling = computed(() => displayEntries.value.length > VIRTUAL_LIST_THRESHOLD);
```

(c) 替换 `openStory` 并新增抽屉/键盘逻辑：

```typescript
function openStory(id: number) {
  markNewsRead(id);
  selectedNewsId.value = id;
  drawerVisible.value = true;
  keyboard.selectedId.value = id;
}

function closeDrawer() {
  drawerVisible.value = false;
  selectedNewsId.value = null;
}

function changeNewsInDrawer(id: number) {
  markNewsRead(id);
  selectedNewsId.value = id;
  keyboard.selectedId.value = id;
}

function openTopic(id: number) {
  router.push({ name: 'topic-detail', params: { id } });
}

function scrollSelectedIntoView(id: number, index: number) {
  if (useVirtualScrolling.value) {
    virtualListRef.value?.scrollToIndex(index);
    return;
  }
  document.querySelector(`[data-news-id="${id}"]`)?.scrollIntoView({ block: 'nearest' });
}

const keyboard = useFeedKeyboard({
  ids: () => displayIds.value,
  isDrawerOpen: () => drawerVisible.value,
  openDrawer: openStory,
  closeDrawer,
  onSelect: scrollSelectedIntoView,
});
```

（`openEvent` 与 router 保留不动。）

(d) template：

- Event Radar 与 Topic Watch 两个 `<SectionCard>` 块整体替换为：

```html
        <div class="grid gap-2.5" data-role="feed-compact-header">
          <EventCapsuleStrip :events="filteredEvents" @open-event="openEvent" />
          <TopicChipsRow :topics="filteredTopics" @open-topic="openTopic" />
        </div>
```

- Raw Stream 区内：虚拟列表分支改为

```html
          <NewsVirtualList
            v-if="useVirtualScrolling"
            ref="virtualListRef"
            :entries="displayEntries"
            :selected-id="keyboard.selectedId.value"
            :read-ids="readIds"
            @open="openStory"
            @visible-ids="visibleStreamIds = $event"
          />
```

非虚拟分支 `v-for` 改遍历 `displayEntries`，NewsCard 加：

```html
                :read="readIds.has(entry.item.id)"
                :selected="entry.item.id === keyboard.selectedId.value"
```

- 列表之后、load-more 哨兵之前加折叠开关：

```html
          <button
            v-if="foldedStream.folded.length"
            type="button"
            class="fold-toggle"
            data-role="news-fold-toggle"
            @click="foldExpanded = !foldExpanded"
          >
            {{ foldExpanded ? '▴ 收起低优先级' : `▾ 已折叠 ${foldedStream.folded.length} 条低优先级 — 展开` }}
          </button>
```

- Raw Stream SectionCard 底部加快捷键提示：

```html
          <p class="kbd-hint" data-role="feed-kbd-hint">
            <kbd>j</kbd>/<kbd>k</kbd> 上下 · <kbd>Enter</kbd> 阅读 · <kbd>Esc</kbd> 关闭
          </p>
```

- 根 `<div class="grid gap-[14px]">` 内最后加抽屉：

```html
    <NewsDetailDrawer
      :newsId="selectedNewsId"
      :visible="drawerVisible"
      :filteredNewsIds="displayIds"
      @close="closeDrawer"
      @changeNews="changeNewsInDrawer"
    />
```

(e) style scoped 追加：

```css
.fold-toggle {
  width: 100%;
  padding: 10px;
  margin-top: 12px;
  border: 1px dashed var(--border);
  border-radius: var(--r-md);
  background: transparent;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
  transition: border-color 140ms ease, color 140ms ease;
}

.fold-toggle:hover {
  border-color: var(--border-strong);
  color: var(--text);
}

.kbd-hint {
  margin: 10px 0 0;
  color: var(--text-faint);
  font-size: 11px;
  text-align: center;
}

.kbd-hint kbd {
  padding: 1px 5px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 10px;
}
```

- [ ] **Step 4: 更新 NewsFeedView.test.ts**

按新结构更新既有断言并补新用例（沿用该文件的 mock 模式：`vi.mock('vue-router')`、reactive 假 store、IntersectionObserver stub）。要点：

```typescript
// 1) 结构断言:三段 SectionCard 断言改为
expect(wrapper.find('[data-role="feed-compact-header"]').exists()).toBe(true);
expect(wrapper.find('[data-role="event-capsule-strip"]').exists()).toBe(true);
expect(wrapper.find('[data-role="topic-chips-row"]').exists()).toBe(true);
expect(wrapper.find('[data-role="event-radar-shell"]').exists()).toBe(false);
expect(wrapper.find('[data-role="topic-watch-shell"]').exists()).toBe(false);

// 2) 点卡片:不再 router.push,改为抽屉收到 newsId
await wrapper.get('[data-role="news-card-shell"]').trigger('click');
expect(mockPush).not.toHaveBeenCalledWith({ name: 'news-detail', params: { id: expect.anything() } });
const drawer = wrapper.findComponent({ name: 'NewsDetailDrawer' });
expect(drawer.props('newsId')).not.toBeNull();

// 3) 事件胶囊:open-event 仍 router.push 到 event-detail(沿用旧断言,目标组件换成 EventCapsuleStrip)

// 4) 折叠:喂 >14 条不同 editorial_score 的 stream,断言 news-fold-toggle 文案含「已折叠」,点击后条目数增加

// 5) 已读:beforeEach 里调 resetReadNewsForTest();点开一条后该卡片 classes 含 news-card--read
```

注意 NewsDetailDrawer 在测试环境需要 stub `RouterLink`（Step 2）与 `newsStore.loadAnalysis`/`analysisMap`——假 store 需补这几个 `vi.fn()`/字段。若 mount 因 `llmStore` 报错，在假 store 集合里补一个 `useLlmStore` mock（`config: null, loadConfig: vi.fn()`）。

- [ ] **Step 5: 跑测试与冒烟**

Run: `cd frontend && npm run test -- --run src/views/NewsFeedView.test.ts src/components/news/NewsVirtualList.test.ts src/smoke/app-navigation.test.ts && npm run typecheck`
Expected: 全部 PASS + typecheck 0 error

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/NewsFeedView.vue frontend/src/components/news/NewsVirtualList.vue frontend/src/components/news/NewsVirtualList.test.ts frontend/src/components/news/NewsDetailDrawer.vue frontend/src/views/NewsFeedView.test.ts
git commit -m "feat(frontend): Latest Events 快读集成——紧凑条/抽屉阅读/键盘流/已读折叠"
```

---

### Task 10: 全量验证（主会话执行，不派子智能体）

- [ ] `conda run -n news-caught pytest backend/tests -q` 全绿
- [ ] `cd frontend && npm run test -- --run` 全绿
- [ ] `cd frontend && npm run typecheck` 0 error
- [ ] `cd frontend && npm run check:api-drift` 退出码 0
- [ ] `make dev` 起服务，浏览器过一遍 `/news`：紧凑条渲染、j/k/Enter/Esc、抽屉连读、已读淡化、折叠展开（用户偏好：本地端口预览）
- [ ] 有问题就地修复后补 commit
