import asyncio
import json
import logging
import pathlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

GOOD_CONDITION_KEYWORDS = [
    "9成新", "95新", "9.5成新", "99新", "9.9成新", "全新", "近全新", "9成以上", "八九成新", "89新",
]
BAD_CONDITION_KEYWORDS = [
    "零件机", "报废", "不开机", "有问题", "故障", "损坏", "主板坏", "进水", "不能用", "无法开机",
]
SOFT_DEFECT_KEYWORDS = [
    "屏碎", "外壳碎", "磕碰", "划痕", "掉漆", "暗病", "轻微问题", "小问题", "电池不耐用", "电池衰减", "缺配件", "无充电器", "无盒",
]
POSITIVE_FUNCTION_KEYWORDS = [
    "功能正常", "一切正常", "无拆无修", "自用", "个人自用", "刚换电池", "可验机", "支持验货", "带发票", "有盒", "配件齐全",
]

# 引流低价词：标题/描述含这些词的商品价格无参考意义，直接过滤
DECOY_PRICE_KEYWORDS = [
    "勿直拍", "勿拍", "展示价", "展示用", "联系改价", "先联系", "先咨询", "请勿直接拍",
    "拍前联系", "拍前咨询", "非卖品", "仅展示", "看好再拍", "价格面议",
]

# 配件/零件词：标题含这些词说明是配件而非整机，直接过滤
ACCESSORY_KEYWORDS = [
    "电池", "充电器", "充电线", "数据线", "外屏", "内屏", "屏幕总成", "液晶屏", "显示屏", "镜头盖",
    "镜头组", "背盖", "后盖", "前盖", "外壳", "机身壳", "按键", "快门按钮", "转接环",
    "存储卡", "内存卡", "sd卡", "cf卡", "相机包", "保护套", "贴膜", "背带", "手柄",
    "闪光灯", "遮光罩", "滤镜", "脚架", "三脚架", "快装板", "热靴", "读卡器",
    "维修", "拆机", "零件", "主板", "传感器", "配件", "说明书", "电子版", "pdf",
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
    quality_score: float = 50.0
    quality_flags: List[str] = field(default_factory=list)
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
            if data.startswith(b"\xef\xbb\xbf"):
                data = data[3:]
            return data.decode("utf-8").strip()
        return ""

    def save_cookie(self, cookie_str: str):
        COOKIE_FILE.write_text(cookie_str.strip(), encoding="utf-8")
        self._cookie_str = cookie_str.strip()
        logger.info("Cookie 已保存")

    def has_storage_state(self) -> bool:
        return STORAGE_STATE_FILE.exists() and STORAGE_STATE_FILE.stat().st_size > 0

    def _parse_cookie_list(self) -> List[dict]:
        cookies = []
        for part in self._cookie_str.split(";"):
            part = part.strip()
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            cookies.append({"name": name.strip(), "value": value.strip(), "domain": ".goofish.com", "path": "/"})
        return cookies

    def _analyze_quality(self, title: str, desc: str) -> Tuple[bool, float, List[str]]:
        text = f"{title} {desc}".lower()
        flags: List[str] = []
        score = 70.0

        # 过滤引流低价商品（勿直拍、展示价等）
        decoy_hits = [kw for kw in DECOY_PRICE_KEYWORDS if kw.lower() in text]
        if decoy_hits:
            score -= min(25.0, 8.0 * len(decoy_hits))
            flags.extend([f"引流低价:{kw}" for kw in decoy_hits[:3]])

        # 过滤配件/零件（电池、外屏、镜头等非整机商品）
        accessory_hits = [kw for kw in ACCESSORY_KEYWORDS if kw.lower() in text]
        if accessory_hits:
            score -= min(35.0, 10.0 * len(accessory_hits))
            flags.extend([f"配件非整机:{kw}" for kw in accessory_hits[:3]])

        hard_hits = [kw for kw in BAD_CONDITION_KEYWORDS if kw.lower() in text]
        if hard_hits:
            score -= min(45.0, 15.0 * len(hard_hits))
            flags.extend([f"功能异常:{kw}" for kw in hard_hits[:3]])

        soft_hits = [kw for kw in SOFT_DEFECT_KEYWORDS if kw.lower() in text]
        if soft_hits:
            score -= min(30.0, 8.0 * len(soft_hits))
            flags.extend([f"外观/配件问题:{kw}" for kw in soft_hits[:3]])

        positive_hits = [kw for kw in POSITIVE_FUNCTION_KEYWORDS if kw.lower() in text]
        if positive_hits:
            score += min(20.0, 6.0 * len(positive_hits))
            flags.extend([f"正向描述:{kw}" for kw in positive_hits[:3]])

        score = max(20.0, min(95.0, score))
        return True, round(score, 2), flags

    def _extract_condition(self, title: str, desc: str) -> str:
        text = f"{title} {desc}"
        for kw in GOOD_CONDITION_KEYWORDS:
            if kw in text:
                return kw
        return "成色未标注"

    def _parse_price(self, price_str: str) -> Optional[float]:
        try:
            v = float(re.sub(r"[^\d.]", "", str(price_str)))
            return v if v > 0 else None
        except Exception:
            return None

    def _extract_items_from_page_data(self, data: dict) -> List[dict]:
        if not isinstance(data, dict):
            return []
        for key in ["resultList", "items", "searchItemList", "itemList"]:
            if key in data and isinstance(data[key], list) and data[key]:
                return data[key]
        for v in data.values():
            if isinstance(v, dict):
                nested = self._extract_items_from_page_data(v)
                if nested:
                    return nested
            elif isinstance(v, list) and len(v) > 2 and all(isinstance(i, dict) for i in v[:3]):
                sample = json.dumps(v[0], ensure_ascii=False)
                if "price" in sample or "title" in sample or "item" in sample:
                    return v
        return []

    def _normalize_item(self, raw: dict, keyword: str = "") -> Optional[XianyuItem]:
        try:
            main = raw.get("data", {}).get("item", {}).get("main", {})
            args = main.get("clickParam", {}).get("args", {})
            ex = main.get("exContent", {})
            detail = ex.get("detailParams", {})

            item_id = str(args.get("item_id") or args.get("id") or "").strip()
            if not item_id:
                return None

            price = self._parse_price(str(args.get("price") or args.get("displayPrice") or "0"))
            if not price:
                return None

            title = detail.get("title", "") or ex.get("title", "") or ""
            if not title:
                return None

            fish_tags = main.get("fishTags", {})
            tags = []
            for row in fish_tags.values():
                if isinstance(row, dict):
                    for tag in row.get("tagList", []):
                        content = tag.get("data", {}).get("content", "")
                        if content:
                            tags.append(content)
            desc = " ".join(tags)

            # 关键词相关性不过滤，只在价格模型中通过离群降权处理
            # （保留 keyword 入参仅用于后续扩展）

            keep, quality_score, quality_flags = self._analyze_quality(title, desc)
            if not keep:
                return None

            sold = "已售" in title or args.get("soldOut") == "true"
            return XianyuItem(
                item_id=item_id,
                title=title,
                price=price,
                condition=self._extract_condition(title, desc),
                description=desc,
                url=f"https://www.goofish.com/item?id={item_id}",
                sold=sold,
                sold_at=datetime.now() if sold else None,
                quality_score=quality_score,
                quality_flags=quality_flags,
            )
        except Exception as e:
            logger.info(f"标准化失败: {e}")
            self._log_raw_item_preview(raw, "标准化异常时的原始数据")
            return None

    def _build_context(self, playwright_browser):
        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800},
        }
        if self.has_storage_state():
            context_kwargs["storage_state"] = str(STORAGE_STATE_FILE)
            return playwright_browser.new_context(**context_kwargs)

        context = playwright_browser.new_context(**context_kwargs)
        cookies = self._parse_cookie_list()
        if cookies:
            context.add_cookies(cookies)
        return context

    def _scrape_sync(self, keyword: str, max_items: int, filter_keyword: Optional[str] = None) -> List[XianyuItem]:
        from playwright.sync_api import sync_playwright

        items: List[XianyuItem] = []
        collected: List[dict] = []
        normalized_count = 0
        filtered_bad_function_count = 0
        response_urls: List[str] = []
        response_statuses: List[dict] = []
        response_ret_samples: List[str] = []
        login_page_hint = False
        risk_page_hint = False

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
            context = self._build_context(browser)
            page = context.new_page()

            def handle_response(response):
                try:
                    if "mtop.taobao.idlemtopsearch.pc.search" not in response.url:
                        return
                    response_urls.append(response.url)
                    response_statuses.append({"url": response.url[:140], "status": response.status})
                    if response.status != 200:
                        return
                    body = response.json()
                    ret = body.get("ret") if isinstance(body, dict) else None
                    if isinstance(ret, list) and ret:
                        response_ret_samples.append(" | ".join([str(x) for x in ret[:2]]))
                    raw_list = self._extract_items_from_page_data(body)
                    if raw_list:
                        collected.extend(raw_list)
                except Exception as e:
                    logger.info(f"响应解析失败: {e}")

            page.on("request", lambda r: None)  # 保留 request 监听占位
            page.on("response", handle_response)
            page.goto(f"https://www.goofish.com/search?q={keyword}", wait_until="networkidle", timeout=30000)
            # 等待足够长让闲鱼两批数据（共60条）都到达
            page.wait_for_timeout(6000)

            # 滚动 HTML 元素（闲鱼真实滚动容器）触发更多数据加载
            for _scroll_i in range(5):
                prev = len(collected)
                page.evaluate("""
                    (() => {
                        // 闲鱼滚动容器是 HTML.page-search
                        const html = document.documentElement;
                        html.scrollTop += 1200;
                        window.scrollBy(0, 1200);
                    })();
                """)
                page.wait_for_timeout(3000)
                if len(collected) == prev:
                    break  # 没有新数据，停止滚动

            if not response_urls:
                page_text = page.content().lower()
                login_page_hint = ("登录" in page_text or "login" in page_text or "请先登录" in page_text)
                risk_page_hint = ("验证码" in page_text or "verify" in page_text or "安全验证" in page_text or "风控" in page_text)

            effective_filter_keyword = filter_keyword or keyword
            for raw in collected:
                item = self._normalize_item(raw, keyword=effective_filter_keyword)
                if not item:
                    filtered_bad_function_count += 1
                    continue
                normalized_count += 1
                items.append(item)

            context.close()
            browser.close()

        quality_scores = [i.quality_score for i in items]
        quality_avg = round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0.0

        self._last_debug_summary = {
            "keyword": keyword,
            "response_count": len(response_urls),
            "response_urls": response_urls[:3],
            "response_statuses": response_statuses[:10],
            "response_ret_samples": response_ret_samples[:5],
            "raw_item_count": len(collected),
            "normalized_count": normalized_count,
            "filtered_bad_function_count": filtered_bad_function_count,
            "filtered_bad_condition_count": filtered_bad_function_count,
            "final_count": len(items),
            "quality_score_avg": quality_avg,
            "has_storage_state": self.has_storage_state(),
            "storage_state_file": str(STORAGE_STATE_FILE),
            "login_page_hint": login_page_hint,
            "risk_page_hint": risk_page_hint,
        }

        if items:
            self._last_debug_summary["final_items_preview"] = [
                {
                    "item_id": item.item_id,
                    "title": item.title,
                    "price": item.price,
                    "quality_score": item.quality_score,
                    "quality_flags": item.quality_flags,
                }
                for item in items[:5]
            ]

        return items[:max_items]

    async def search(
        self,
        keyword: str,
        max_items: int = 20,
        cookie_override: Optional[str] = None,
        filter_keyword: Optional[str] = None,
    ) -> List[XianyuItem]:
        if cookie_override and cookie_override.strip():
            self.save_cookie(cookie_override.strip())

        import concurrent.futures
        import threading

        def _run_in_new_thread():
            # 在全新线程里运行，确保没有残留的 asyncio 事件循环干扰 Playwright
            result = []
            exc = []
            def _target():
                try:
                    result.extend(self._scrape_sync(keyword, max_items, filter_keyword))
                except Exception as e:
                    exc.append(e)
            t = threading.Thread(target=_target, daemon=True)
            t.start()
            t.join(timeout=90)
            if exc:
                raise exc[0]
            return result

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, _run_in_new_thread)


_crawler_instance: Optional[XianyuCrawler] = None


def get_crawler() -> XianyuCrawler:
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = XianyuCrawler()
    return _crawler_instance
