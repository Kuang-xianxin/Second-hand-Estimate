import asyncio
import re
import json
import logging
import pathlib
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

GOOD_CONDITION_KEYWORDS = [
    "9成新", "95新", "9.5成新", "99新", "9.9成新", "全新", "近全新",
    "9成以上", "八九成新", "89新"
]
BAD_CONDITION_KEYWORDS = [
    "零件机", "维修", "配件", "报废", "外壳碎", "屏碎", "不开机",
    "有问题", "故障", "损坏", "拆机", "废品", "6成新", "5成新", "4成新"
]

BASE_DIR = pathlib.Path(__file__).resolve().parents[2]
COOKIE_FILE = BASE_DIR / "xianyu_cookies.txt"
STORAGE_STATE_FILE = BASE_DIR / "xianyu_storage_state.json"


@dataclass
class XianyuItem:
    item_id: str
    title: str
    price: float
    condition: str
    description: str
    url: str
    sold: bool
    sold_at: Optional[datetime]
    crawled_at: datetime = field(default_factory=datetime.now)


class XianyuCrawler:
    def __init__(self):
        self._cookie_str = self._load_cookie()
        self._last_debug_summary = {}

    def _log_raw_item_preview(self, raw: dict, prefix: str):
        try:
            preview = json.dumps(raw, ensure_ascii=False)[:500]
            logger.info(f"{prefix}: {preview}")
        except Exception as e:
            logger.info(f"{prefix}: <无法序列化原始数据: {e}>")

    def _load_cookie(self) -> str:
        if COOKIE_FILE.exists():
            data = COOKIE_FILE.read_bytes()
            if data.startswith(b'\xef\xbb\xbf'):
                data = data[3:]
            return data.decode('utf-8').strip()
        return ""

    def save_cookie(self, cookie_str: str):
        COOKIE_FILE.write_text(cookie_str.strip(), encoding='utf-8')
        self._cookie_str = cookie_str.strip()
        logger.info("Cookie 已保存")

    def has_storage_state(self) -> bool:
        return STORAGE_STATE_FILE.exists() and STORAGE_STATE_FILE.stat().st_size > 0

    def _parse_cookie_list(self) -> List[dict]:
        cookies = []
        for part in self._cookie_str.split(';'):
            part = part.strip()
            if '=' not in part:
                continue
            name, value = part.split('=', 1)
            cookies.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': '.goofish.com',
                'path': '/',
            })
        return cookies

    def _is_good_condition(self, title: str, desc: str) -> bool:
        text = title + desc
        return not any(kw in text for kw in BAD_CONDITION_KEYWORDS)

    def _extract_condition(self, title: str, desc: str) -> str:
        text = title + desc
        for kw in GOOD_CONDITION_KEYWORDS:
            if kw in text:
                return kw
        return "成色未标注"

    def _parse_price(self, price_str: str) -> Optional[float]:
        try:
            s = re.sub(r"[^\d.]", "", str(price_str))
            v = float(s)
            return v if v > 0 else None
        except Exception:
            return None

    def _extract_items_from_page_data(self, data: dict) -> List[dict]:
        if not isinstance(data, dict):
            return []
        for key in ['resultList', 'items', 'searchItemList', 'itemList']:
            if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                return data[key]
        for v in data.values():
            if isinstance(v, dict):
                result = self._extract_items_from_page_data(v)
                if result:
                    return result
            elif isinstance(v, list) and len(v) > 2:
                if all(isinstance(i, dict) for i in v[:3]):
                    sample = json.dumps(v[0], ensure_ascii=False)
                    if 'price' in sample or 'title' in sample or 'item' in sample:
                        return v
        return []

    def _normalize_item(self, raw: dict) -> Optional[XianyuItem]:
        try:
            main = raw.get('data', {}).get('item', {}).get('main', {})
            args = main.get('clickParam', {}).get('args', {})
            ex = main.get('exContent', {})
            detail = ex.get('detailParams', {})

            item_id = str(args.get('item_id') or args.get('id') or '').strip()
            if not item_id:
                logger.info("跳过原始商品：缺少 item_id")
                self._log_raw_item_preview(raw, "缺少 item_id 的原始数据")
                return None

            price = self._parse_price(str(args.get('price') or args.get('displayPrice') or '0'))
            if not price:
                logger.info(f"跳过原始商品 {item_id}：价格解析失败")
                self._log_raw_item_preview(raw, f"商品 {item_id} 价格解析失败的原始数据")
                return None

            title = detail.get('title', '') or ex.get('title', '') or ''
            if not title:
                logger.info(f"跳过原始商品 {item_id}：缺少标题")
                self._log_raw_item_preview(raw, f"商品 {item_id} 缺少标题的原始数据")
                return None

            fish_tags = main.get('fishTags', {})
            tag_texts = []
            for row in fish_tags.values():
                if isinstance(row, dict):
                    for tag in row.get('tagList', []):
                        content = tag.get('data', {}).get('content', '')
                        if content:
                            tag_texts.append(content)
            desc = ' '.join(tag_texts)

            sold = '已售' in title or args.get('soldOut') == 'true'
            condition = self._extract_condition(title, desc)

            return XianyuItem(
                item_id=item_id,
                title=title,
                price=price,
                condition=condition,
                description=desc,
                url=f"https://www.goofish.com/item?id={item_id}",
                sold=sold,
                sold_at=datetime.now() if sold else None,
            )
        except Exception as e:
            logger.info(f"标准化失败: {e}")
            self._log_raw_item_preview(raw, "标准化异常时的原始数据")
            return None

    def _build_context(self, playwright_browser):
        context_kwargs = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'viewport': {'width': 1280, 'height': 800},
        }
        if self.has_storage_state():
            logger.info(f"使用 storage_state 登录态: {STORAGE_STATE_FILE}")
            context_kwargs['storage_state'] = str(STORAGE_STATE_FILE)
            context = playwright_browser.new_context(**context_kwargs)
        else:
            logger.info("未找到 storage_state，退回 Cookie 注入模式")
            context = playwright_browser.new_context(**context_kwargs)
            cookies = self._parse_cookie_list()
            if cookies:
                context.add_cookies(cookies)
        return context

    def _scrape_sync(self, keyword: str, max_items: int) -> List[XianyuItem]:
        from playwright.sync_api import sync_playwright

        items: List[XianyuItem] = []
        collected_responses: List[dict] = []
        normalized_count = 0
        filtered_bad_condition_count = 0
        response_urls: List[str] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                ],
            )
            context = self._build_context(browser)
            page = context.new_page()

            def handle_response(response):
                try:
                    if 'mtop.taobao.idlemtopsearch.pc.search' not in response.url:
                        return
                    response_urls.append(response.url)
                    logger.info(f"命中搜索接口: {response.url}")
                    if response.status != 200:
                        logger.info(f"搜索接口状态异常: {response.status}")
                        return
                    body = response.json()
                    raw_list = self._extract_items_from_page_data(body)
                    if raw_list:
                        logger.info(f"拦截到搜索响应，包含 {len(raw_list)} 条数据")
                        self._log_raw_item_preview(raw_list[0], "搜索响应首条原始数据")
                        collected_responses.extend(raw_list)
                    else:
                        logger.info(f"搜索响应已命中但未提取到列表，响应顶层 keys: {list(body.keys())[:20]}")
                except Exception as e:
                    logger.info(f"响应解析失败: {e}")

            page.on('response', handle_response)

            url = f"https://www.goofish.com/search?q={keyword}"
            logger.info(f"访问: {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(3000)

            if not response_urls:
                logger.info("本次未命中任何搜索接口响应")

            for raw in collected_responses:
                item = self._normalize_item(raw)
                if not item:
                    continue
                normalized_count += 1
                if self._is_good_condition(item.title, item.description):
                    items.append(item)
                else:
                    filtered_bad_condition_count += 1
                    logger.info(f"商品被成色过滤: {item.item_id} | {item.title}")

            context.close()
            browser.close()

        logger.info(
            f"搜索'{keyword}'调试汇总: 命中响应 {len(response_urls)} 个, 原始商品 {len(collected_responses)} 条, "
            f"标准化成功 {normalized_count} 条, 成色过滤 {filtered_bad_condition_count} 条, 最终有效 {len(items)} 条"
        )
        self._last_debug_summary = {
            "keyword": keyword,
            "response_count": len(response_urls),
            "response_urls": response_urls[:3],
            "raw_item_count": len(collected_responses),
            "normalized_count": normalized_count,
            "filtered_bad_condition_count": filtered_bad_condition_count,
            "final_count": len(items),
            "has_storage_state": self.has_storage_state(),
            "storage_state_file": str(STORAGE_STATE_FILE),
        }
        if items:
            preview = [
                {
                    "item_id": item.item_id,
                    "title": item.title,
                    "price": item.price,
                }
                for item in items[:5]
            ]
            self._last_debug_summary["final_items_preview"] = preview
            logger.info(
                "最终有效商品预览: " + " | ".join(
                    [f"{item.item_id}:{item.title[:20]}:¥{item.price}" for item in items[:5]]
                )
            )
        logger.info(f"搜索'{keyword}'共获取 {len(items)} 个有效商品")
        return items[:max_items]

    async def search(
        self,
        keyword: str,
        max_items: int = 20,
        cookie_override: Optional[str] = None,
    ) -> List[XianyuItem]:
        if cookie_override and cookie_override.strip():
            self.save_cookie(cookie_override.strip())

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._scrape_sync, keyword, max_items)


_crawler_instance: Optional[XianyuCrawler] = None


def get_crawler() -> XianyuCrawler:
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = XianyuCrawler()
    return _crawler_instance
