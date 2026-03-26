import asyncio
import sys
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

sys.path.insert(0, r'd:\cursor项目文件\估二手\backend')
from app.crawler.xianyu import XianyuCrawler

async def test():
    c = XianyuCrawler()
    items = await c.search('iPhone 14', max_items=10)
    print(f'\n=== 获取到 {len(items)} 条数据 ===')
    for i in items[:10]:
        print(f'  [{i.item_id}] {i.title[:40]} - ¥{i.price} [{i.condition}]')

asyncio.run(test())
