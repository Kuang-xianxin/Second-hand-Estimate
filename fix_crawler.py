import pathlib

p = pathlib.Path(r'd:\cursor项目文件\估二手\backend\app\crawler\xianyu.py')
content = p.read_text(encoding='utf-8')

old = '''    def _normalize_item(self, raw: dict) -> Optional[XianyuItem]:
        try:
            # 尝试多种数据结构
            data = raw.get('data', raw)
            item_data = data.get('item', data)
            main = item_data.get('main', item_data)
            click = main.get('clickParam', {}).get('args', {})

            item_id = str(
                click.get('item_id') or click.get('itemId') or
                data.get('itemId') or raw.get('itemId') or
                raw.get('id') or ''
            ).strip()

            title_obj = main.get('title', {})
            title = (
                title_obj.get('text', '') if isinstance(title_obj, dict)
                else str(title_obj)
            ) or raw.get('title', '') or data.get('title', '')

            price_raw = (
                main.get('price') or main.get('fishPrice') or
                raw.get('price') or data.get('price') or '0'
            )
            price = self._parse_price(str(price_raw))
            if not price:
                return None

            desc_obj = main.get('desc', {})
            desc = (
                desc_obj.get('text', '') if isinstance(desc_obj, dict)
                else str(desc_obj)
            ) or ''

            if not item_id:
                item_id = f"unk_{abs(hash(title + str(price)))}"

            sold = '已售' in title or '已售' in desc
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
            logger.debug(f"标准化失败: {e}")
            return None'''

new = '''    def _normalize_item(self, raw: dict) -> Optional[XianyuItem]:
        try:
            main = raw.get('data', {}).get('item', {}).get('main', {})
            args = main.get('clickParam', {}).get('args', {})
            ex = main.get('exContent', {})
            detail = ex.get('detailParams', {})

            item_id = str(args.get('item_id') or args.get('id') or '').strip()
            if not item_id:
                return None

            price = self._parse_price(str(args.get('price') or args.get('displayPrice') or '0'))
            if not price:
                return None

            title = detail.get('title', '') or ex.get('title', '') or ''
            if not title:
                return None

            # 从 fishTags 提取成色标签
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
            logger.debug(f"标准化失败: {e}")
            return None'''

if old in content:
    content = content.replace(old, new)
    p.write_text(content, encoding='utf-8')
    print('替换成功')
else:
    print('未找到目标字符串，尝试部分匹配...')
    # 找到方法开头
    idx = content.find('def _normalize_item')
    print(f'方法位置: {idx}')
    print(repr(content[idx:idx+100]))
