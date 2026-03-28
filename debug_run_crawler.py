import asyncio
import sys
import traceback

sys.path.insert(0, r'd:\cursor项目文件\估二手\backend')
from app.crawler.xianyu import XianyuCrawler

async def main():
    try:
        items = await XianyuCrawler().search('iphone', max_items=10)
        print('OK', len(items))
        for item in items[:3]:
            print(item.title, item.price)
    except Exception as e:
        print('ERR', repr(e))
        traceback.print_exc()

asyncio.run(main())
