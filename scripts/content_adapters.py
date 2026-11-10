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
    if layout_id != 'content-blue-112' or content.get('texts'):
        return dict(content), None
    items = content.get('items')
    if content.get('type') != 'cards' or not isinstance(items, list) or len(items) != 4:
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
    adapted['item_count'] = 4
    return adapted, 'four_card_items_to_p112'
