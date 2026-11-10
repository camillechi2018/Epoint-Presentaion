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
    # These layouts were visually reviewed for cross-scenario reuse. Every
    # explanatory field below comes from the request; only ordinal markers are
    # computed. A missing conclusion, outcome, or tag rejects the adapter.
    new_contracts = {
        'content-blue-060': ('process', 4, ('title', 'body', 'outcome'), ('goal',)),
        'content-blue-267': ('process', 4, ('title', 'body'), ()),
        'content-tech-026': ('comparison', 4, ('title', 'body'), ('summary',)),
        'content-tech-029': ('comparison', 2, ('title', 'body'), ('summary', 'conclusion')),
        'content-tech-040': ('comparison', 2, ('title', 'body', 'tags'), ('summary',)),
        'content-tech-048': ('cards', 4, ('title', 'body'), ('summary', 'conclusion')),
        'content-tech-033': ('cards', 5, ('title', 'body'), ('summary', 'conclusion')),
        'content-tech-054': ('process', 4, ('title', 'body'), ('summary',)),
        'content-tech-063': ('milestone_timeline', 5, ('label', 'body'), ('summary',)),
        'content-tech-064': ('milestone_timeline', 5, ('label', 'title'), ('summary',)),
        'content-tech-065': ('milestone_timeline', 5, ('label', 'body'), ('summary',)),
        'content-tech-034': ('cards', 5, ('title', 'body'), ('summary',)),
        'content-tech-037': ('cards', 3, ('title', 'body'), ('summary',)),
        'content-tech-038': ('process', 4, ('title', 'body'), ('summary',)),
        'content-tech-043': ('cards', 3, ('title', 'body'), ('summary',)),
        'content-tech-020': ('cards', 6, ('title',), ('summary', 'center.topic')),
    }
    if layout_id in new_contracts and not content.get('texts'):
        kind, count, required, extras = new_contracts[layout_id]
        items = content.get('items')
        title = content.get('title') or page_title
        def extra_value(path):
            value = content
            for part in path.split('.'):
                value = value.get(part) if isinstance(value, dict) else None
            return value
        valid = (content.get('type') == kind and isinstance(items, list) and len(items) == count
                 and isinstance(title, str) and title.strip()
                 and all(isinstance(extra_value(key), str) and extra_value(key).strip() for key in extras)
                 and all(isinstance(item, dict) and all(
                     isinstance(item.get(key), str) and item[key].strip()
                     if key != 'tags' else isinstance(item.get('tags'), list) and len(item['tags']) == 2
                     and all(isinstance(tag, str) and tag.strip() for tag in item['tags'])
                     for key in required) for item in items))
        if not valid:
            return dict(content), None
        texts = {'page.title' if layout_id.startswith('content-blue-') else 'heading': title}
        if layout_id == 'content-blue-060':
            texts['page.goal'] = content['goal']
            for i, item in enumerate(items):
                prefix = f'steps[{i}]'
                texts.update({f'{prefix}.number': f'{i+1:02d}', f'{prefix}.title': item['title'],
                              f'{prefix}.body': item['body'], f'{prefix}.outcome': item['outcome']})
        elif layout_id == 'content-blue-267':
            for i, item in enumerate(items):
                texts.update({f'steps[{i}].heading': item['title'], f'steps[{i}].body': item['body']})
        elif layout_id == 'content-tech-026':
            texts['summary'] = content['summary']
            for i, item in enumerate(items, 1):
                texts.update({f'issue_{i}.number': f'{i:02d}', f'issue_{i}.title': item['title'],
                              f'issue_{i}.body': item['body']})
        elif layout_id in ('content-tech-029', 'content-tech-040'):
            texts['summary'] = content['summary']
            for key, item in zip(('left', 'right'), items):
                texts.update({f'{key}.title': item['title'], f'{key}.body': item['body']})
                if layout_id == 'content-tech-040':
                    texts.update({f'{key}.tag_1': item['tags'][0], f'{key}.tag_2': item['tags'][1]})
            if layout_id == 'content-tech-029':
                texts['bottom.conclusion'] = content['conclusion']
        elif layout_id == 'content-tech-033':
            # The source labels are swapped: bottom_conclusion renders as the
            # page heading, and heading renders as the bottom takeaway.
            texts.update({'heading': content['conclusion'], 'bottom_conclusion': title,
                          'summary': content['summary']})
            for i, item in enumerate(items, 1):
                texts.update({f'item_{i}.title': item['title'], f'item_{i}.body': item['body']})
        elif layout_id == 'content-tech-054':
            texts['summary'] = content['summary']
            for i, item in enumerate(items, 1):
                texts.update({f'item_{i}.title': item['title'], f'item_{i}.body': item['body'],
                              f'item_{i}.number': f'{i:02d}'})
        elif layout_id in ('content-tech-063', 'content-tech-064', 'content-tech-065'):
            texts['summary'] = content['summary']
            for i, item in enumerate(items, 1):
                if layout_id == 'content-tech-064':
                    texts.update({f'item_{i}.year': item['label'], f'item_{i}.event': item['title']})
                else:
                    prefix = f'milestone_{i}'
                    texts.update({f'{prefix}.body': item['body'],
                                  f'{prefix}.year' if layout_id.endswith('063') else f'{prefix}.date': item['label']})
        elif layout_id in ('content-tech-034', 'content-tech-037',
                           'content-tech-038', 'content-tech-043'):
            texts['summary'] = content['summary']
            for i, item in enumerate(items, 1):
                texts.update({f'item_{i}.title': item['title'], f'item_{i}.body': item['body']})
                if layout_id == 'content-tech-038':
                    texts[f'item_{i}.number'] = f'{i:02d}'
        elif layout_id == 'content-tech-020':
            texts.update({'summary': content['summary'], 'center.topic': content['center']['topic']})
            for i, item in enumerate(items):
                side = 'left' if i < 3 else 'right'
                texts[f'{side}_{i % 3 + 1}.title'] = item['title']
        else:  # P048's title and body binding indices have different source order.
            texts.update({'summary': content['summary'], 'top_conclusion': content['conclusion']})
            for i, (title_index, body_index) in enumerate(zip((3, 4, 2, 1), (2, 1, 3, 4))):
                item = items[i]
                texts.update({f'item_{title_index}.title': item['title'],
                              f'item_{body_index}.body': item['body']})
        adapted = dict(content)
        adapted['texts'] = texts
        if layout_id == 'content-tech-038':
            # The source's variable-column path is an unverified internal
            # prototype. Reuse only its fixed four reviewed text slots.
            adapted.pop('items', None)
            adapted.pop('item_count', None)
            return adapted, f'{kind}_{count}_to_{layout_id}'
        # P026 has four reviewed issue slots but its old cardinality rule has
        # no source_count; an explicit item_count would be read as reflow.
        if layout_id != 'content-tech-026':
            adapted['item_count'] = count
        return adapted, f'{kind}_{count}_to_{layout_id}'
    if layout_id in ('content-blue-181', 'content-blue-199') and not content.get('texts'):
        items = content.get('items')
        title = content.get('title') or page_title
        is_layers = layout_id.endswith('181')
        expected_type = 'hierarchy' if is_layers else 'milestone_timeline'
        required = ('title', 'body') if is_layers else ('label', 'title', 'body')
        if (content.get('type') == expected_type and isinstance(items, list)
                and len(items) == (4 if is_layers else 5)
                and isinstance(title, str) and title.strip()
                and (not is_layers or content.get('order') == 'inner_to_outer')
                and all(isinstance(item, dict) and all(isinstance(item.get(key), str)
                        and item[key].strip() for key in required) for item in items)):
            texts = {'page.title': title}
            for index, item in enumerate(items):
                prefix = f'layers[{index}]' if is_layers else f'years[{index}]'
                texts[f'{prefix}.heading'] = item['title']
                texts[f'{prefix}.body'] = item['body']
                if not is_layers:
                    texts[f'{prefix}.label'] = item['label']
            adapted = dict(content)
            adapted['texts'] = texts
            adapted['item_count'] = len(items)
            return adapted, ('four_nested_layers_to_p181' if is_layers
                             else 'five_year_milestones_to_p199')
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
