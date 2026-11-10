"""Lossless mappings from generic body data to verified template fields."""
from __future__ import annotations


def classify_trial_failure(message: str) -> str:
    if any(word in message for word in ('缺少字段', '缺少必需', '须提供', '需要提供')):
        return 'MISSING_REQUIRED_FIELD'
    if any(word in message for word in ('容量', '视觉宽度', '允许行数', '溢出')):
        return 'TEXT_OVER_CAPACITY'
    if any(word in message for word in ('图片区域', '图片槽', '替换内容图片')):
        return 'IMAGE_SLOT_MISMATCH'
    if any(word in message for word in ('数量', '项数', 'item_count')):
        return 'ITEM_COUNT_MISMATCH'
    return 'TRIAL_REJECTED'


def adapt_for_layout(layout_id: str, content: dict, page_title: str | None = None) -> tuple[dict, str | None]:
    """Return a copied payload; never split, invent, or summarize user facts."""
    if layout_id in ('content-blue-256', 'content-blue-258') and not content.get('texts'):
        items = content.get('items')
        title = content.get('title') or page_title
        if (content.get('type') == 'process' and isinstance(items, list) and len(items) == 4
                and isinstance(title, str) and title.strip()
                and all(isinstance(item, dict) and all(isinstance(item.get(key), str)
                        and item[key].strip() for key in ('title', 'body')) for item in items)):
            texts = {'page.title': title}
            for index, item in enumerate(items):
                texts[f'steps[{index}].heading'] = item['title']
                texts[f'steps[{index}].body'] = item['body']
            adapted = dict(content)
            adapted['texts'] = texts
            adapted['item_count'] = 4
            adapted['generic_visual'] = True
            return adapted, 'four_process_items_to_p' + layout_id.rsplit('-', 1)[-1]
    if layout_id == 'content-blue-142' and not content.get('texts'):
        items = content.get('items')
        center = content.get('center')
        title = content.get('title') or page_title
        if (content.get('type') == 'cards' and isinstance(items, list) and len(items) == 4
                and isinstance(center, dict) and isinstance(center.get('title'), str)
                and center['title'].strip() and isinstance(title, str) and title.strip()
                and all(isinstance(item, dict) and all(isinstance(item.get(key), str)
                        and item[key].strip() for key in ('title', 'body')) for item in items)):
            texts = {'page.title': title, 'center.title': center['title']}
            for index, item in enumerate(items):
                texts[f'items[{index}].heading'] = item['title']
                texts[f'items[{index}].body'] = item['body']
            adapted = dict(content)
            adapted['texts'] = texts
            adapted['item_count'] = 4
            return adapted, 'four_cards_with_center_to_p142'
    if layout_id == 'content-blue-076' and not content.get('texts'):
        directions = content.get('items')
        center = content.get('center')
        title = content.get('title') or page_title
        if (content.get('type') == 'directions' and isinstance(directions, list)
                and len(directions) == 4 and isinstance(center, dict)
                and isinstance(center.get('title'), str) and center['title'].strip()
                and isinstance(title, str) and title.strip()
                and all(isinstance(item, dict) and all(isinstance(item.get(key), str)
                        and item[key].strip() for key in ('heading', 'body', 'short'))
                        for item in directions)):
            texts = {'page.title': title, 'center.title': center['title']}
            for index, item in enumerate(directions):
                for key in ('heading', 'body', 'short'):
                    texts[f'directions[{index}].{key}'] = item[key]
            adapted = dict(content)
            adapted['texts'] = texts
            adapted['item_count'] = 4
            return adapted, 'four_directions_with_center_to_p076'
    if layout_id not in ('content-blue-112', 'content-blue-106') or content.get('texts'):
        return dict(content), None
    items = content.get('items')
    required_count = 4 if layout_id == 'content-blue-112' else 5
    if content.get('type') != 'cards' or not isinstance(items, list) or len(items) != required_count:
        return dict(content), None
    title = content.get('title') or page_title
    if not isinstance(title, str) or not title.strip():
        return dict(content), None
    texts = {'page.title': title}
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key].strip()
                                                    for key in ('title', 'body')):
            return dict(content), None
        texts[f'items[{index}].heading'] = item['title']
        texts[f'items[{index}].body'] = item['body']
    adapted = dict(content)
    adapted['texts'] = texts
    adapted['item_count'] = required_count
    adapted['generic_visual'] = True
    return adapted, ('four_card_items_to_p112' if required_count == 4
                     else 'five_card_items_to_p106')
