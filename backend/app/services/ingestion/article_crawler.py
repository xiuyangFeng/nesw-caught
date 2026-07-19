import logging

from bs4 import BeautifulSoup

from app.services.http_pool import get_crawl_client

logger = logging.getLogger(__name__)

def crawl_and_extract_article(url: str, timeout: float = 15.0) -> str:
    """给定网页 URL，异步爬取页面并智能提取干净的段落正文。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    logger.info("article crawl started: url=%s", url)
    try:
        # 使用共享连接池抓取网页（httpx.Client 线程安全，支持自动重定向）
        client = get_crawl_client()
        response = client.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        html = response.text
    except Exception as exc:
        logger.warning("Failed to fetch article webpage from %s: %s", url, exc)
        raise RuntimeError(f"Webpage fetch failed: {exc}") from exc

    try:
        soup = BeautifulSoup(html, "html.parser")

        # 去除干扰性标签
        for s in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript"]):
            s.decompose()

        # 精确正文区域选择器策略
        selectors = [
            "article",
            ".article-content",
            ".post-content",
            ".entry-content",
            ".content-main",
            "#article-body",
            ".article-body",
            ".article-detail",
            ".main-content",
            "#content",
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text("\n").strip()
                # 简单过滤，如果长度足够，说明抽取正常
                if len(text) > 120:
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    result = "\n\n".join(lines)
                    logger.info(
                        "article crawl succeeded: url=%s selector=%s length=%s", url, selector, len(result)
                    )
                    return result

        # 密度兜底法：合并独立段落标签内容
        paragraphs = []
        # 提取 p 标签和有文本的 div 标签
        for element in soup.find_all(["p", "div"]):
            text = element.get_text().strip()
            # 过滤干扰文本（如版权声明、非常短的句段）
            if not text or len(text) < 25:
                continue
            if "版权所有" in text or "ICP备" in text or "Copyright" in text:
                continue

            if element.name == "p":
                paragraphs.append(text)
            elif element.name == "div" and not element.find(["p", "div"]):
                # 如果是底层 div（不包含其它段落），也计入
                paragraphs.append(text)

        if paragraphs:
            result = "\n\n".join(paragraphs)
            logger.info("article crawl succeeded: url=%s selector=density_fallback length=%s", url, len(result))
            return result

        # 终极兜底：直接提取 body 中的去除空行后的文字
        if soup.body:
            text = soup.body.get_text("\n").strip()
        else:
            text = soup.get_text("\n").strip()

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        result = "\n\n".join(lines)
        logger.info("article crawl succeeded: url=%s selector=body_fallback length=%s", url, len(result))
        return result
    except Exception as exc:
        logger.error("Failed to parse article content from %s: %s", url, exc)
        raise RuntimeError(f"Webpage parse failed: {exc}") from exc
