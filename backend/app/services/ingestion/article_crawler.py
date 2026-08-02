import logging
import re
import threading
from contextlib import contextmanager

from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.services.http_pool import get_crawl_client

logger = logging.getLogger(__name__)


def _configured_crawl_timeout(default: float = 15.0) -> float:
    """单次网页抓取的默认超时（秒），读取 settings.crawl_timeout_seconds。

    此前是硬编码 15.0 的模块常量；改为跟随配置，配置不可用时退回历史默认值。
    """
    try:
        return float(get_settings().crawl_timeout_seconds)
    except Exception:  # pragma: no cover - 配置不可用时退回默认值
        return default


DEFAULT_CRAWL_TIMEOUT_SECONDS = _configured_crawl_timeout()

try:
    import lxml  # noqa: F401
    _BS4_PARSER = "lxml"
except ImportError:
    _BS4_PARSER = "html.parser"


# ---------------------------------------------------------------------------
# 解析背压（parse backpressure）
#
# 抓取正文分两段，对 GIL 的表现完全相反：
#   1) 网络抓取：httpx 在 socket 上阻塞时释放 GIL，8 并发（news_crawl_max_workers）
#      有真实收益，也不会影响其它线程；
#   2) HTML 解析：BeautifulSoup 建树 + decompose + 选择器匹配 + get_text 是纯 CPU，
#      全程持有 GIL（实测单次解析 cpu/wall ≈ 1.00）。8 个爬取线程同时进入这一段，
#      会把 uvicorn 事件循环和处理普通只读请求的 anyio 线程一起饿死——表现就是
#      「后台爬正文时点一下卡一秒」。
#
# 所以这里用一个独立的、容量更小的模块级信号量把解析阶段单独限流：网络仍按
# news_crawl_max_workers 并发，解析最多 news_crawl_parse_concurrency 个线程同时进行。
# 信号量是模块级共享的——进程内所有调用方（管线线程池、手动重跑脚本等）共用同一个
# 配额，否则各自开池仍会把 CPU 抢满。
# ---------------------------------------------------------------------------
DEFAULT_PARSE_CONCURRENCY = 2

_parse_semaphore_lock = threading.Lock()
# (容量, 信号量)；容量随配置变化时重建，便于测试与运行期改配置
_parse_semaphore_state: tuple[int, threading.BoundedSemaphore] | None = None


def _configured_parse_concurrency() -> int:
    try:
        value = int(get_settings().news_crawl_parse_concurrency)
    except Exception:  # pragma: no cover - 配置不可用时退回默认值
        return DEFAULT_PARSE_CONCURRENCY
    return max(value, 1)


def _get_parse_semaphore() -> threading.BoundedSemaphore:
    """返回当前配置容量对应的解析信号量（容量变化时重建）。"""
    global _parse_semaphore_state
    capacity = _configured_parse_concurrency()
    with _parse_semaphore_lock:
        state = _parse_semaphore_state
        if state is None or state[0] != capacity:
            state = (capacity, threading.BoundedSemaphore(capacity))
            _parse_semaphore_state = state
        return state[1]


def reset_parse_semaphore() -> None:
    """丢弃缓存的信号量，下次取用时按最新配置重建（供测试使用）。"""
    global _parse_semaphore_state
    with _parse_semaphore_lock:
        _parse_semaphore_state = None


@contextmanager
def parse_slot():
    """进入 HTML 解析临界区；超出并发配额的线程在此排队等待。

    注意这里是无超时的阻塞获取：解析本身很快（毫秒到百毫秒级），排队时间有界；
    引入获取超时反而会把「等一会儿」变成「这条正文抓取失败」，改变既有语义。
    """
    semaphore = _get_parse_semaphore()
    semaphore.acquire()
    try:
        yield
    finally:
        semaphore.release()


DEFAULT_MAX_HTML_CHARS = 1_000_000


def _configured_max_html_chars() -> int:
    try:
        return int(get_settings().news_crawl_max_html_chars)
    except Exception:  # pragma: no cover - 配置不可用时退回默认值
        return DEFAULT_MAX_HTML_CHARS


def _truncate_oversized_html(html: str, *, url: str) -> str:
    """超大页面在解析前截断，避免个别巨页长时间独占解析槽位拖垮整批。

    选择「截断后继续解析」而不是「整条判失败」：正文通常位于文档前部，截断后
    多半仍能抽到有效内容；即便抽不到，也会照常走既有的质量闸门落成 failed。
    """
    limit = _configured_max_html_chars()
    if limit <= 0 or len(html) <= limit:
        return html
    logger.warning(
        "article html truncated before parse: url=%s length=%s limit=%s", url, len(html), limit
    )
    return html[:limit]


class ArticleQualityError(RuntimeError):
    """正文抽取结果未通过质量闸门（登录墙 / 验证码 / JS 空壳 / 纯导航样板）。

    单独成类是为了让上层能把这类结果记为 failed 并允许重试，
    而不是像以前那样把垃圾文本标成 success 形成永久坏数据。
    """


# ---------------------------------------------------------------------------
# 编码嗅探
#
# 旧实现用 `response.apparent_encoding` —— 那是 requests 的属性，httpx.Response
# 根本没有，getattr 恒为 None；而 httpx 的 `.encoding` 在无 charset 头时返回
# "utf-8"，也永远不会是 "iso-8859-1"。于是「智能解码」对 httpx 是彻底的空操作，
# 代码从不读取 HTML 的 <meta charset>，GBK/GB2312 页面（东方财富/同花顺/证券时报）
# 一律按 utf-8 解码成 `���` 乱码，且 extract_status 仍是 success。
# ---------------------------------------------------------------------------
_META_CHARSET_RE = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([a-zA-Z0-9_\-]+)""", re.IGNORECASE)
# 编码别名归一化：gb2312/gbk 实际内容常含 GB18030 扩展字符，统一按 gb18030 解更稳
_ENCODING_ALIASES = {
    "gb2312": "gb18030",
    "gbk": "gb18030",
    "gb-2312": "gb18030",
    "iso-8859-1": "utf-8",
    "latin-1": "utf-8",
    "latin1": "utf-8",
}
# 只扫描头部若干字节：<meta charset> 按规范必须出现在文档前 1024 字节内，留一倍余量
_META_SNIFF_BYTES = 2048


def _normalize_encoding(name: str | None) -> str | None:
    if not name or not isinstance(name, str):
        return None
    key = name.strip().strip("\"'").lower()
    if not key:
        return None
    return _ENCODING_ALIASES.get(key, key)


def _sniff_meta_charset(content: bytes) -> str | None:
    """从 HTML 头部字节里嗅探 <meta charset> / <meta http-equiv=Content-Type>。"""
    match = _META_CHARSET_RE.search(content[:_META_SNIFF_BYTES])
    if not match:
        return None
    try:
        return _normalize_encoding(match.group(1).decode("ascii", errors="ignore"))
    except Exception:  # pragma: no cover - 防御性
        return None


def _header_charset(response) -> str | None:
    """响应头里显式声明的 charset（可信度最高）。

    httpx 用 `charset_encoding` 暴露它：没有 charset 头时是 None，
    不像 `.encoding` 会自作主张返回 "utf-8"。
    """
    charset = getattr(response, "charset_encoding", None)
    if isinstance(charset, str) and charset.strip():
        return _normalize_encoding(charset)

    # 兼容不提供 charset_encoding 的假响应/其它 http 客户端：自己从 Content-Type 里取
    headers = getattr(response, "headers", None)
    if headers is not None:
        try:
            content_type = headers.get("Content-Type") or headers.get("content-type") or ""
        except Exception:  # pragma: no cover - headers 可能是任意假对象
            content_type = ""
        match = re.search(r"charset\s*=\s*([a-zA-Z0-9_\-]+)", str(content_type), re.IGNORECASE)
        if match:
            return _normalize_encoding(match.group(1))
    return None


def _decode_response_html(response) -> str:
    """智能解码 HTTP 响应内容：响应头 charset > meta charset > utf-8。"""
    content = getattr(response, "content", None)
    if not isinstance(content, (bytes, bytearray)):
        return getattr(response, "text", "") or ""
    content = bytes(content)

    candidates: list[str] = []
    for candidate in (_header_charset(response), _sniff_meta_charset(content), "utf-8"):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for encoding in candidates:
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    # 全部严格解码失败：按优先级最高的候选做替换式解码，至少保住可读部分
    for encoding in candidates:
        try:
            return content.decode(encoding, errors="replace")
        except LookupError:
            continue
    return content.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# 正文质量闸门
#
# 旧的 body 兜底只要页面有任何文字就返回非空，于是登录墙/付费墙/JS 空壳/验证码页
# 的导航文字被标成 success，作为"正文"喂给 LLM 分类器污染信号；又因为是 success，
# 后续永不重试，形成永久坏数据。这里给兜底结果加最小质量判定。
# ---------------------------------------------------------------------------

# 登录 / 付费 / 验证码 / 反爬拦截页的特征词
_BLOCKED_PAGE_MARKERS = (
    "请登录", "立即登录", "登录后查看", "登录后继续", "免费注册", "扫码登录",
    "订阅后阅读", "开通会员", "付费阅读", "会员专享",
    "请输入验证码", "人机验证", "安全验证", "滑动验证", "访问受限", "访问被拒绝",
    "请开启javascript", "请启用javascript",
    "sign in to continue", "please sign in", "please log in", "log in to continue",
    "subscribe to continue", "subscribers only", "become a member",
    "are you a robot", "verify you are human", "access denied", "403 forbidden",
    "enable javascript", "javascript is disabled", "checking your browser",
)

# 导航 / 页脚样板词：命中过多说明抽到的是框架而不是正文
_BOILERPLATE_MARKERS = (
    "首页", "登录", "注册", "关于我们", "联系我们", "隐私政策", "用户协议", "免责声明",
    "网站地图", "友情链接", "客服", "下载app", "关注我们", "意见反馈", "举报",
    "home", "sign in", "sign up", "log in", "register", "about us", "contact us",
    "privacy policy", "terms of service", "cookie", "newsletter", "subscribe",
    "follow us", "all rights reserved", "site map",
)

# 兜底正文的最小可用长度：低于这个长度基本不可能是一篇新闻
_MIN_FALLBACK_LENGTH = 200
# 有效字符（中文 + 拉丁字母）占比下限：低于此值多半是符号/导航碎片堆
_MIN_MEANINGFUL_RATIO = 0.35
# 样板词命中数上限（按每千字归一化后）
_MAX_BOILERPLATE_HITS = 6
# 长文里偶尔出现「登录 / subscribe」属正常引用，只在短文本上把它当拦截页信号
_BLOCKED_MARKER_MAX_LENGTH = 800

_MEANINGFUL_CHAR_RE = re.compile(r"[一-鿿A-Za-z]")


def _blocked_page_reason(text: str) -> str | None:
    """短文本里命中登录/付费/验证码特征词 → 判定为拦截页。"""
    if len(text) > _BLOCKED_MARKER_MAX_LENGTH:
        return None
    lowered = text.lower()
    for marker in _BLOCKED_PAGE_MARKERS:
        if marker in lowered:
            return f"blocked_page_marker({marker})"
    return None


def _assess_fallback_quality(text: str, *, url: str) -> str | None:
    """判定 body 兜底正文是否可信；返回 None 表示通过，否则返回不通过的原因。"""
    stripped = (text or "").strip()
    if len(stripped) < _MIN_FALLBACK_LENGTH:
        return f"too_short(len={len(stripped)})"

    meaningful = len(_MEANINGFUL_CHAR_RE.findall(stripped))
    ratio = meaningful / len(stripped)
    if ratio < _MIN_MEANINGFUL_RATIO:
        return f"low_text_ratio({ratio:.2f})"

    blocked = _blocked_page_reason(stripped)
    if blocked:
        return blocked

    lowered = stripped.lower()
    hits = sum(1 for marker in _BOILERPLATE_MARKERS if marker in lowered)
    # 长文里偶尔出现"关于我们"很正常，按每 1000 字归一化后再判定
    normalized_hits = hits / max(len(stripped) / 1000, 1.0)
    if normalized_hits > _MAX_BOILERPLATE_HITS:
        logger.debug("article fallback boilerplate dense: url=%s hits=%s", url, hits)
        return f"boilerplate_dense(hits={hits})"

    return None


# 精确正文区域选择器策略（集成国内外主流财经媒体 DOM 选择器）。
# 顺序即优先级：越靠前越"专指正文"，通用容器排在后面，避免误伤既有站点。
ARTICLE_CONTENT_SELECTORS = (
    "article",
    "#artibody",            # 新浪财经
    ".detail-content",      # 财联社详情页
    ".rich-text",           # 华尔街见闻
    ".article-content",
    ".articleDetail-content",  # 36Kr 详情页
    ".common-width.margin-bottom-20",  # 36Kr 正文容器
    ".post-content",
    ".entry-content",
    ".content-main",
    "#article-body",
    ".article-body",
    ".article-detail",
    ".caas-body",           # 雅虎财经
    ".ArticleBody-articleBody",  # CNBC
    ".article__body",       # MarketWatch
    "#js-article__body",    # MarketWatch
    ".paywall",             # MarketWatch/Barron's 正文容器
    ".main-content",
    "#content",
    "#articleContent",      # 东方财富
    ".article-txt",         # 同花顺
    ".news_body",           # 腾讯/网易
    ".art_content",         # 证券时报
    ".content_area",        # 证券时报备用
    ".index-module_articleContent",  # 部分 Next.js 财经站
)


# ---------------------------------------------------------------------------
# 正文容器定位：单趟索引取代 24 次 select_one
#
# 上面这张选择器表按优先级逐个 `soup.select_one(sel)` 时，soupsieve 每次都要
# 重新遍历整棵文档树。实测 550KB 页面（约 1 万个标签）：建树 87ms、decompose
# 12ms，而 24 次 select_one 合计 457ms —— 选择器扫描才是解析阶段最大的单项开销，
# 且这一段是纯 Python、全程持有 GIL，正是后台爬正文时点击变卡的主因。
#
# 这些选择器全是「简单选择器」（标签名 / #id / .class / .class1.class2），
# 完全可以用一趟文档遍历建立 id/class 倒排索引后统一解析，语义与 select_one
# 一致：都返回文档序中的第一个匹配元素。无法识别的复杂选择器仍回退到
# select_one，保证以后往表里加复杂选择器时不会静默失效。
# ---------------------------------------------------------------------------
_SIMPLE_SELECTOR_RE = re.compile(r"^(?P<tag>[A-Za-z][\w-]*)?(?P<rest>(?:[.#][A-Za-z_][\w-]*)+)?$")
_SELECTOR_TOKEN_RE = re.compile(r"[.#][A-Za-z_][\w-]*")


def _compile_simple_selector(selector: str):
    """把简单选择器编译成 (标签名, id, class 集合)；不可识别时返回 None。"""
    match = _SIMPLE_SELECTOR_RE.match(selector.strip())
    if not match or not (match.group("tag") or match.group("rest")):
        return None
    ids: list[str] = []
    classes: list[str] = []
    for token in _SELECTOR_TOKEN_RE.findall(match.group("rest") or ""):
        (ids if token[0] == "#" else classes).append(token[1:])
    if len(ids) > 1:  # `#a#b` 这类退化写法交给 soupsieve
        return None
    # HTML 里标签名大小写不敏感（html.parser 已统一小写），id/class 大小写敏感
    tag = (match.group("tag") or "").lower() or None
    return tag, (ids[0] if ids else None), frozenset(classes)


_COMPILED_CONTENT_SELECTORS = tuple(
    (selector, _compile_simple_selector(selector)) for selector in ARTICLE_CONTENT_SELECTORS
)
# 只索引选择器真正用到的 id/class，避免为文档里成千上万个无关 class 建表
_INDEXED_IDS = frozenset(
    compiled[1] for _, compiled in _COMPILED_CONTENT_SELECTORS if compiled and compiled[1]
)
_INDEXED_CLASSES = frozenset(
    name for _, compiled in _COMPILED_CONTENT_SELECTORS if compiled for name in compiled[2]
)


def _element_classes(element) -> frozenset[str]:
    value = element.attrs.get("class")
    if not value:
        return frozenset()
    if isinstance(value, str):  # 个别解析器把 class 当单值属性返回
        return frozenset(value.split())
    return frozenset(value)


class _ContentElementIndex:
    """按需构建的 id/class 倒排索引，保持文档序。

    索引是惰性的：优先级最高的 `article` 是纯标签选择器，走 `soup.find` 就能命中，
    绝大多数带 <article> 的页面根本不会触发建索引这一趟遍历。
    """

    def __init__(self, soup) -> None:
        self._soup = soup
        self._by_id: dict[str, list] = {}
        self._by_class: dict[str, list] = {}
        self._built = False

    def _build(self) -> None:
        if self._built:
            return
        self._built = True
        for element in self._soup.find_all(True):
            attrs = element.attrs
            element_id = attrs.get("id")
            if isinstance(element_id, str) and element_id in _INDEXED_IDS:
                self._by_id.setdefault(element_id, []).append(element)
            classes = _element_classes(element)
            if classes:
                for name in classes & _INDEXED_CLASSES:
                    self._by_class.setdefault(name, []).append(element)

    @staticmethod
    def _matches(element, tag: str | None, classes: frozenset[str]) -> bool:
        if tag is not None and element.name != tag:
            return False
        return not classes or classes <= _element_classes(element)

    def find_first(self, compiled) -> object | None:
        tag, element_id, classes = compiled
        if element_id is not None:
            self._build()
            candidates = self._by_id.get(element_id, ())
        elif classes:
            self._build()
            # 任取一个 class 做索引键，再逐个校验其余约束（多 class 选择器很少）
            candidates = self._by_class.get(next(iter(classes)), ())
        else:
            # 纯标签选择器：find 就是文档序第一个，无需建索引
            return self._soup.find(tag)
        for element in candidates:
            if self._matches(element, tag, classes):
                return element
        return None


def select_article_container(soup):
    """按优先级返回第一个「文本足够长」的正文容器文本，没有则返回 (None, None)。

    返回 (selector, text)，与旧实现逐个 select_one 的结果完全一致。
    """
    index = _ContentElementIndex(soup)
    for selector, compiled in _COMPILED_CONTENT_SELECTORS:
        try:
            element = index.find_first(compiled) if compiled else soup.select_one(selector)
        except Exception:  # pragma: no cover - 个别选择器语法不被解析器支持时跳过
            continue
        if element is None:
            continue
        text = element.get_text("\n").strip()
        # 简单过滤，如果长度足够，说明抽取正常
        if len(text) > 120:
            return selector, text
    return None, None


def _fetch_article_html(url: str, timeout: float) -> str:
    """阶段 A：网络抓取（阻塞在 socket 上，释放 GIL，可高并发）。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        # 使用共享连接池抓取网页（httpx.Client 线程安全，支持自动重定向）
        client = get_crawl_client()
        response = client.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return _decode_response_html(response)
    except Exception as exc:
        detail = str(exc).strip() or type(exc).__name__
        logger.warning("Failed to fetch article webpage from %s: %s: %s", url, type(exc).__name__, detail)
        raise RuntimeError(f"Webpage fetch failed: {type(exc).__name__}: {detail}") from exc


def crawl_and_extract_article(url: str, timeout: float = DEFAULT_CRAWL_TIMEOUT_SECONDS) -> str:
    """给定网页 URL，爬取页面并智能提取干净的段落正文。

    分两段执行：网络抓取按 news_crawl_max_workers 高并发；HTML 解析（纯 CPU、
    持有 GIL）在模块级信号量下限流到 news_crawl_parse_concurrency，避免饿死
    uvicorn 事件循环。抽取结果与状态机语义与拆分前完全一致。
    """
    logger.info("article crawl started: url=%s", url)
    html = _fetch_article_html(url, timeout)
    # —— 网络到此结束，下面是纯 CPU 段，必须排队 ——
    with parse_slot():
        return _extract_article_text(html, url=url)


def _extract_article_text(html: str, *, url: str) -> str:
    """阶段 B：HTML 解析与正文抽取（纯 CPU，调用方需持有解析信号量）。"""
    html = _truncate_oversized_html(html, url=url)
    try:
        soup = BeautifulSoup(html, _BS4_PARSER)

        # 去除干扰性标签
        for s in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript"]):
            s.decompose()

        selector, text = select_article_container(soup)
        if text is not None:
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            result = "\n\n".join(lines)
            logger.info(
                "article crawl succeeded: url=%s selector=%s length=%s", url, selector, len(result)
            )
            return result

        # 密度兜底法：合并独立段落标签内容（增加去重保护）
        paragraphs = []
        seen_paras: set[str] = set()
        # 提取 p 标签和有文本的 div 标签
        for element in soup.find_all(["p", "div"]):
            text = element.get_text().strip()
            # 过滤干扰文本（如版权声明、非常短的句段）
            if not text or len(text) < 25:
                continue
            if "版权所有" in text or "ICP备" in text or "Copyright" in text:
                continue
            if text in seen_paras:
                continue

            if element.name == "p":
                seen_paras.add(text)
                paragraphs.append(text)
            elif element.name == "div" and not element.find(["p", "div"]):
                # 如果是底层 div（不包含其它段落），也计入
                seen_paras.add(text)
                paragraphs.append(text)

        if paragraphs:
            result = "\n\n".join(paragraphs)
            # 密度兜底沿用既有的宽松长度策略（短正文也可能是有效快讯），
            # 但登录墙 / 验证码这类明确的拦截页必须拦下，否则会被标成 success 且永不重试。
            blocked = _blocked_page_reason(result)
            if blocked is not None:
                logger.warning(
                    "article crawl rejected by quality gate: url=%s reason=%s stage=density_fallback length=%s",
                    url,
                    blocked,
                    len(result),
                )
                raise ArticleQualityError(f"Extracted content failed quality gate: {blocked}")
            logger.info("article crawl succeeded: url=%s selector=density_fallback length=%s", url, len(result))
            return result

        # 终极兜底：直接提取 body 中的去除空行后的文字。
        # 这一层最容易抓到登录墙 / 验证码 / JS 空壳页的框架文字，必须过质量闸门。
        if soup.body:
            text = soup.body.get_text("\n").strip()
        else:
            text = soup.get_text("\n").strip()

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        result = "\n\n".join(lines)
        reason = _assess_fallback_quality(result, url=url)
        if reason is not None:
            logger.warning(
                "article crawl rejected by quality gate: url=%s reason=%s length=%s", url, reason, len(result)
            )
            raise ArticleQualityError(f"Extracted content failed quality gate: {reason}")

        logger.info("article crawl succeeded: url=%s selector=body_fallback length=%s", url, len(result))
        return result
    except ArticleQualityError:
        # 质量闸门是明确结论，不能被下面的通用 except 改写成 "parse failed"
        raise
    except Exception as exc:
        logger.exception("Failed to parse article content from %s: %s", url, exc)
        raise RuntimeError(f"Webpage parse failed: {exc}") from exc
