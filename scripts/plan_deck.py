"""Global deck selection for the isolated next-generation component library."""
from __future__ import annotations
import argparse, json, random, re, unicodedata
from collections import Counter
from pathlib import Path
from library_location import get_library
from relation_match import canonical, load_taxonomy, match_relation, match_role
from fallback_rules import fallback_type, fallback_catalog
from content_adapters import adapt_for_layout
from capacity_preflight import preflight


def semantic_fit(page, entry):
    """Small deterministic bonus from curated layout labels, never a hard gate."""
    label=entry.get('search_label','')
    if not label or entry.get('role') in ('cover','directory','section','closing'):
        return 0
    query=' '.join(str(page.get(key,'')) for key in ('purpose','title'))
    def terms(value):
        chunks=re.findall(r'[\u3400-\u9fff]+|[a-zA-Z0-9]+',value.casefold())
        return {part for chunk in chunks for part in
                ([chunk[i:i+2] for i in range(len(chunk)-1)] if '\u3400'<=chunk[0]<='\u9fff' else [chunk])}
    return min(4,len(terms(query)&terms(label)))

def load(root: Path):
    return json.loads((root/'catalog.json').read_text(encoding='utf-8-sig'))


# Older request examples used this marker to force a drawn page. It is not a
# catalog ID and must not suppress a later, newly verified template match.
NO_TEMPLATE_MARKERS = frozenset({'no-verified-template-for-this-relation'})
CONTENT_RELATIONS = {
    'metrics': 'metrics', 'comparison': 'comparison', 'process': 'process',
    'bullets': 'parallel-points', 'cards': 'parallel-points',
    'data_table': 'data-table', 'milestone_timeline': 'timeline',
    'hierarchy': 'framework',
}


def normalize_body_request(page):
    """Recover a generic relation and count from structured body content."""
    page = dict(page)
    notes = []
    if page.get('role') not in ('cover', 'directory', 'section', 'closing'):
        if page.get('layout_id') in NO_TEMPLATE_MARKERS:
            page.pop('layout_id')
            notes.append('removed_legacy_no_template_marker')
        content = page.get('content') if isinstance(page.get('content'), dict) else {}
        if not page.get('information_relation'):
            relation = CONTENT_RELATIONS.get(content.get('type'))
            if relation:
                page['information_relation'] = relation
                notes.append('relation_from_content_type')
        need = dict(page.get('needs') or {})
        if need.get('item_count') is None and isinstance(content.get('items'), list) and content['items']:
            need['item_count'] = len(content['items'])
            page['needs'] = need
            notes.append('item_count_from_content_items')
    return page, notes


def count_profile(entry, root):
    """Use recorded fixed-count evidence when old layouts lack verified_counts."""
    rules=json.loads((root/entry['layout_rules']).read_text(encoding='utf-8'))
    verified=rules.get('verified_counts')
    if isinstance(verified,list):
        return verified,rules.get('source_count')
    source_count=rules.get('source_count')
    supported=rules.get('supported_counts',[])
    if entry.get('classification_status')=='verified' and rules.get('cardinality_mode')=='fixed' \
            and supported==[source_count] and type(source_count) is int:
        return supported,source_count
    if entry.get('classification_status')=='verified' and entry.get('semantic_review'):
        review=json.loads((root/entry['semantic_review']).read_text(encoding='utf-8'))
        count=review.get('source_item_count')
        if review.get('normal_use_status')=='static_pptx_verified_draft' and type(count) is int and count>0:
            return [count],count
    return [],source_count


def binding_gap(entry, page, root, theme):
    """Count fields not yet mapped by an explicitly prepared template payload."""
    content = page.get('content') if isinstance(page.get('content'), dict) else {}
    content, _ = adapt_for_layout(entry['id'], content, page.get('title'), entry=entry)
    texts = content.get('texts') if isinstance(content.get('texts'), dict) else {}
    binding_rel = entry.get('red_bindings') if theme == 'red' and entry.get('red_bindings') else entry['bindings']
    fields = json.loads((root / binding_rel).read_text(encoding='utf-8-sig'))['fields']
    provided = set(texts)
    return sum(field['field'] not in provided and field.get('semantic_path') not in provided
               for field in fields if field.get('semantic_role') not in
               ('brand_locked', 'decoration_locked', 'computed_item_count') and field['field'] != 'brand')

def content_is_four_cards(page):
    content = page.get('content')
    return (page.get('role') in (None, 'body', 'content', 'summary')
            and page.get('information_relation') in (None, 'parallel-points', 'summary')
            and isinstance(content, dict) and content.get('type') == 'cards'
            and isinstance(content.get('items'), list) and len(content['items']) == 4)


STRUCTURAL_RELATION_GROUPS = {
    'parallel-points': {'parallel-points', 'summary', 'framework'},
    'framework': {'parallel-points', 'framework', 'hierarchy', 'summary'},
    'summary': {'parallel-points', 'summary'},
    'ordered-steps': {'process', 'ordered-steps'},
    'process': {'process', 'ordered-steps'},
    'comparison': {'comparison'}, 'hierarchy': {'hierarchy', 'framework'},
    'cycle': {'cycle'}, 'timeline': {'timeline'}, 'schedule': {'schedule'},
    'single-focus': {'single-focus'},
}


def structural_relation_compatible(entry, page):
    structure = (entry.get('matching_contract') or {}).get('structure_type')
    requested = page.get('matching_relation') or page.get('information_relation')
    return not requested or requested in STRUCTURAL_RELATION_GROUPS.get(structure, {requested})


def matches_structural_contract(entry, page, taxonomy):
    """Opt-in structural reuse; an unreviewed entry retains legacy matching."""
    contract = entry.get('matching_contract') or {}
    if contract.get('policy') != 'structural':
        return False
    if page.get('role') not in (None, 'body', 'content', 'summary', 'parallel'):
        return False
    if entry.get('matching_activation') == 'structure_ready' and not structural_relation_compatible(entry, page):
        return False
    content = page.get('content') if isinstance(page.get('content'), dict) else {}
    if entry.get('matching_activation') == 'structure_ready':
        from content_adapters import adapt_structural_fields
        content, _ = adapt_structural_fields(entry, content, page.get('title'))
    # Existing curated requests carry the exact binding paths and an explicit
    # layout ID. Keep that path available; the real fill still validates each field.
    if (page.get('layout_id') == entry.get('id') and isinstance(content.get('texts'), dict)
            and content['texts']):
        return True
    # The field-complete route lets any reviewed structural page be reused
    # without matching the source deck's business vocabulary. Its actual
    # geometry and text limits are still enforced by fill_layout.
    if (entry.get('matching_activation') in ('structure_ready', 'pilot_verified')
            and content.get('type') == 'template_fields'
            and content.get('structure_type') == contract.get('structure_type')
            and isinstance(content.get('texts'), dict)):
        required = contract.get('required_binding_paths', [])
        return bool(required and all(isinstance(content['texts'].get(path), str)
                                     and content['texts'][path].strip() for path in required))
    if entry.get('matching_activation') != 'pilot_verified':
        return False
    requested_relation = canonical(page.get('information_relation'), taxonomy)
    compatible = contract.get('compatible_relations', [])
    if requested_relation and compatible and requested_relation not in compatible:
        return False
    if content.get('type') not in contract.get('content_types', []):
        return False
    items = content.get('items')
    if not isinstance(items, list) or len(items) not in contract.get('verified_counts', []):
        return False
    if not isinstance(content.get('title') or page.get('title'), str) or not (content.get('title') or page.get('title')).strip():
        return False
    def valid_item_field(item, key):
        value = item.get(key)
        if key == 'tags' and contract.get('item_tag_count'):
            return (isinstance(value, list) and len(value) == contract['item_tag_count']
                    and all(isinstance(tag, str) and tag.strip() for tag in value))
        return isinstance(value, str) and bool(value.strip())
    if not all(isinstance(item, dict) and all(valid_item_field(item, key)
               for key in contract.get('item_fields', [])) for item in items):
        return False
    if contract.get('required_order') and content.get('order') != contract['required_order']:
        return False
    if contract.get('label_sequence') == 'ascending_years':
        import re
        labels = [re.fullmatch(r'(\d{4})年?', item['label'].strip()) for item in items]
        if any(label is None for label in labels):
            return False
        years = [int(label.group(1)) for label in labels]
        if years != sorted(set(years)):
            return False
    if contract.get('label_sequence') == 'ascending_dates':
        import re
        dates = [re.fullmatch(r'(\d{4})年(1[0-2]|[1-9])月', item['label'].strip()) for item in items]
        if any(date is None for date in dates):
            return False
        pairs = [(int(date.group(1)), int(date.group(2))) for date in dates]
        if pairs != sorted(set(pairs)):
            return False
    for path in contract.get('required_content_fields', []):
        value = content
        for part in path.split('.'):
            value = value.get(part) if isinstance(value, dict) else None
        if not isinstance(value, str) or not value.strip():
            return False
    return True


def matches_structural_discovery(entry, page, taxonomy, root=None):
    """Find a reviewed layout by geometry before checking template-specific fields."""
    contract = entry.get('matching_contract') or {}
    if contract.get('policy') != 'structural':
        return False
    if entry.get('matching_activation') != 'structure_ready':
        return matches_structural_contract(entry, page, taxonomy)
    if page.get('role') in ('cover', 'directory', 'section', 'closing'):
        return False
    if not structural_relation_compatible(entry, page):
        return False
    content = page.get('content') if isinstance(page.get('content'), dict) else {}
    # A flat list of prose has no independently supplied title/body pairs,
    # center topic, or other nested slots. Discover it only when the existing
    # lossless adapter can actually map every required field. Rich structured
    # inputs still enter discovery before field mapping for diagnostics.
    items = content.get('items')
    if (content.get('type') == 'bullets' and isinstance(items, list) and items
            and all(isinstance(item, str) for item in items)
            and not content.get('texts')):
        from content_adapters import adapt_structural_fields
        _, adapter = adapt_structural_fields(entry, content, page.get('title'))
        if adapter is None:
            return False
    if root is not None and isinstance(content.get('items'), list):
        counts, _ = count_profile(entry, root)
        if len(content['items']) not in counts:
            return False
    if matches_structural_contract(entry, page, taxonomy):
        return True
    structure = contract.get('structure_type')
    declared = content.get('structure_type')
    if declared and declared != structure:
        return False
    if not declared:
        # These are structural relations, not original deck business labels.
        compatible = {
            'cards': {'parallel-points', 'framework', 'summary'},
            'bullets': {'parallel-points', 'summary'},
            'process': {'process', 'ordered-steps'},
            'comparison': {'comparison'},
            'hierarchy': {'hierarchy', 'framework'},
            'cycle': {'cycle'},
            'timeline': {'timeline'},
            'milestone_timeline': {'timeline'},
            'schedule': {'schedule'},
            'single_focus': {'single-focus'},
        }
        if structure not in compatible.get(content.get('type'), set()):
            return False
    items = content.get('items')
    if isinstance(items, list):
        actual_count = len(items)
    else:
        actual_count = (page.get('needs') or {}).get('item_count')
    if type(actual_count) is not int or actual_count < 1:
        return False
    if root is not None:
        counts, _ = count_profile(entry, root)
        if actual_count not in counts:
            return False
    return True


def matches_strict_contract(entry, page):
    contract = entry.get('matching_contract') or {}
    if contract.get('policy', entry.get('matching_policy')) != 'semantic_strict':
        return True
    content = page.get('content') if isinstance(page.get('content'), dict) else {}
    # Some classified strict layouts still have no registered invariant.
    # Their source relation may be a broad label such as parallel-points;
    # that label alone cannot authorize a generic automatic fill.
    if not contract.get('required_relation') and not contract.get('exact_binding_relations'):
        return bool(page.get('layout_id') == entry.get('id')
                    and isinstance(content.get('texts'), dict) and content['texts'])
    if (page.get('layout_id') == entry.get('id') and isinstance(content.get('texts'), dict)
            and content['texts'] and page.get('information_relation') in contract.get('exact_binding_relations', [])):
        return True
    return page.get('information_relation') == contract.get('required_relation', entry.get('information_relation'))


def matches_structural_relation(entry, page, taxonomy):
    """Reuse verified generic geometry across source business names, not topology."""
    # A catalog classification is an inventory result, not permission to
    # auto-map arbitrary input into this layout. Only an activated, reviewed
    # contract may soften the source-business relation gate.
    if (entry.get('matching_activation') != 'pilot_verified'
            or (entry.get('matching_contract') or {}).get('policy') != 'structural'
            or page.get('role') in ('cover', 'directory', 'section', 'closing')):
        return False
    requested = canonical(page.get('matching_relation') or page.get('information_relation'), taxonomy)
    if requested is None:
        content = page.get('content') if isinstance(page.get('content'), dict) else {}
        requested = canonical(CONTENT_RELATIONS.get(content.get('type')), taxonomy)
    return bool(requested and requested == entry.get('canonical_relation'))

def eligible(e, p, request, taxonomy):
    reasons=[]
    requested_style=p.get('style_family',request.get('style_family'))
    if requested_style:
        if (e.get('style_family') or 'legacy-blue-red')!=requested_style:reasons.append('style_family')
    elif e.get('style_family')=='deep-blue-tech':
        reasons.append('style_family_not_selected')
    specified=p.get('layout_id')==e['id']
    if p.get('layout_id') and not specified: return ['other_layout']
    if e.get('status')!='approved' and not request.get('allow_draft'): reasons.append('draft')
    classification=e.get('classification_status')
    reviewed_draft=classification=='visual_reviewed' and request.get('allow_visual_reviewed') and request.get('allow_draft')
    if classification!='verified' and not reviewed_draft and not (specified and request.get('allow_provisional')):
        reasons.append('unverified_classification')
    if e.get('media_status')=='missing-source-image':reasons.append('missing_source_image')
    if str(e.get('pptx_support','')).startswith('blocked_'):reasons.append('pptx_blocked')
    relation=p.get('matching_relation') or p.get('information_relation')
    structural_match = matches_structural_discovery(e, p, taxonomy, request['_root'])
    structural_relation_match = matches_structural_relation(e, p, taxonomy)
    contract = e.get('matching_contract') or {}
    if e.get('matching_policy') == 'data_contract':
        payload = p.get('content') if isinstance(p.get('content'), dict) else {}
        if payload.get('type') not in ('metrics', 'chart', 'data_table', 'table', 'template_fields'):
            reasons.append('data_contract')
    strict_content=p.get('content') if isinstance(p.get('content'),dict) else {}
    strict_exact=(specified and isinstance(strict_content.get('texts'),dict) and bool(strict_content['texts'])
                  and p.get('information_relation') in contract.get('exact_binding_relations',[]))
    strict_match = (contract.get('policy') == 'semantic_strict'
                    and (p.get('information_relation') == contract.get('required_relation') or strict_exact))
    if (e.get('matching_contract') or {}).get('policy') == 'structural' and not structural_match:
        reasons.append('structure_contract')
    if not match_role(e,p.get('role'),relation,taxonomy) and not (structural_match or structural_relation_match or strict_match):reasons.append('role')
    relation_matches = match_relation(e,relation,taxonomy)
    if not relation_matches and (structural_match or structural_relation_match):
        relation_matches = True
    if not relation_matches and strict_match:
        relation_matches = True
    if not relation_matches:reasons.append('relation')
    if not matches_strict_contract(e,p):reasons.append('semantic_invariant')
    theme=p.get('theme',request.get('theme'))
    if theme and theme not in e.get('themes',[]):reasons.append('theme')
    if p.get('format','pptx') in ('html','both') and e.get('html_support')!='verified':reasons.append('html_unavailable')
    if p.get('motion_required') and e.get('motion_support')!='verified':reasons.append('motion_unavailable')
    need=p.get('needs',{});cap=e.get('capacity',{})
    if need.get('body_slots',0)>cap.get('body_slots',0):reasons.append('text_capacity')
    title_chars=need.get('title_chars')
    if title_chars is None and isinstance(p.get('title'),str):title_chars=len(p['title'])
    if title_chars is not None:
        if type(title_chars) is not int or title_chars<1:reasons.append('invalid_title_length')
        elif e.get('title_pressure_status')=='tested_short_copy_only':
            rules=json.loads((request['_root']/e['layout_rules']).read_text(encoding='utf-8'))
            if title_chars>rules.get('title_pressure_test',{}).get('safe_title_chars',0):reasons.append('title_over_capacity')
        if isinstance(p.get('title'),str) and e.get('role') in ('cover','directory','section','closing'):
            binding_rel=e.get('red_bindings') if theme=='red' and e.get('red_bindings') else e.get('bindings')
            fields=json.loads((request['_root']/binding_rel).read_text(encoding='utf-8'))['fields']
            aliases={'cover':('cover.title',),'closing':('closing.title',),
                     'section':('chapter.title','section.title'),
                     'directory':('page.title',)}.get(e.get('role'),())
            title_field=next((x for x in fields if x.get('semantic_path') in aliases),None)
            if title_field:
                lines=p['title'].split('\n')
                units=lambda line:sum(2 if unicodedata.east_asian_width(ch) in ('W','F') else 1 for ch in line)
                if len(p['title'])>title_field.get('max_chars',9999) or len(lines)>title_field.get('max_lines',1) or any(units(line)>title_field.get('max_width_units',100) for line in lines):
                    reasons.append('title_over_verified_width')
    if need.get('item_count') is not None:
        rules_path=e.get('layout_rules')
        if not rules_path:reasons.append('count_rules_missing')
        else:
            available_counts,_=count_profile(e,request['_root'])
            if need['item_count'] not in available_counts:reasons.append('item_count_unverified')
    if e.get('role')=='directory' and isinstance(p.get('items'),list):
        items=p['items']
        rules=json.loads((request['_root']/e['layout_rules']).read_text(encoding='utf-8'))
        if len(items) not in rules.get('verified_counts',[]) or (need.get('item_count') is not None and need['item_count']!=len(items)):
            reasons.append('item_count_unverified')
        elif rules.get('directory_item_fields'):
            binding_rel=e.get('red_bindings') if theme=='red' and e.get('red_bindings') else e['bindings']
            bindings=json.loads((request['_root']/binding_rel).read_text(encoding='utf-8'))['fields']
            field_limits={field['field']:field for field in bindings}
            for index,item in enumerate(items):
                fields=rules['directory_item_fields'][min(index,len(rules['directory_item_fields'])-1)]
                if not isinstance(item,dict):reasons.append('invalid_directory_item');break
                for role,field in fields.items():
                    if role=='number':continue
                    value=item.get(role)
                    limit=field_limits.get(field,{})
                    if not isinstance(value,str) or not value.strip():
                        reasons.append('missing_directory_field');break
                    lines=value.split('\n')
                    width=lambda line:sum(2 if unicodedata.east_asian_width(ch) in ('W','F') else 1 for ch in line)
                    if len(value)>limit.get('max_chars',9999) or len(lines)>limit.get('max_lines',9999) or any(width(line)>limit.get('max_width_units',9999) for line in lines):
                        reasons.append('directory_text_over_capacity');break
                if any(reason in reasons for reason in ('missing_directory_field','directory_text_over_capacity')):break
    if e.get('role')=='data-chart' and not p.get('data_source'):reasons.append('data_source_missing')
    return reasons

def resolve(library,request):
    root=Path(library).resolve();catalog=load(root);taxonomy=load_taxonomy(root,catalog);request=dict(request);request['_root']=root
    seed=request.get('seed',0)
    if type(seed) is not int:raise ValueError('seed必须是整数')
    pages=request.get('pages')
    if not isinstance(pages,list) or not pages:raise ValueError('pages必须是非空数组')
    rng=random.Random(seed);chosen=[];family_usage=Counter();layout_usage=Counter();section_layout_id=None
    for index,p in enumerate(pages,1):
        if not isinstance(p,dict) or not str(p.get('purpose','')).strip():raise ValueError(f'第{index}页缺少purpose')
        p,normalization=normalize_body_request(p);need=dict(p.get('needs') or {})
        content=p.get('content') if isinstance(p.get('content'),dict) else {}
        relation=p.get('information_relation')
        if relation and canonical(relation,taxonomy) is None:
            generic=CONTENT_RELATIONS.get(content.get('type'))
            if generic:
                p['matching_relation']=generic
                normalization.append('generic_relation_from_content_type_for_candidate_search')
        if 'items' in p:
            if not isinstance(p['items'],list):raise ValueError(f'第{index}页items必须是数组')
            if need.get('item_count') is not None and need['item_count']!=len(p['items']):
                raise ValueError(f'第{index}页item_count与items实际数量不一致')
            need['item_count']=len(p['items'])
        if need.get('item_count') is not None and (type(need['item_count']) is not int or need['item_count']<1):
            raise ValueError(f'第{index}页item_count必须是正整数')
        p['needs']=need
        rejected=Counter();candidates=[]
        for e in catalog['layouts']:
            reasons=eligible(e,p,request,taxonomy)
            if reasons: rejected.update(reasons)
            else:candidates.append(e)
        if p.get('role')=='section' and section_layout_id is not None:
            candidates=[e for e in candidates if e['id']==section_layout_id]
            if not candidates:
                raise ValueError(f'第{index}页无法沿用整稿章节版式 {section_layout_id}；请调整章节文案或为全部章节重选同一版式。')
        if not candidates:
            if p.get('role') in ('cover','directory','section','closing'):
                raise ValueError(f'第{index}页结构页没有合格版式；排除原因：{dict(rejected)}。')
            content = p.get('content') if isinstance(p.get('content'), dict) else {}
            inferred = fallback_type(content) if content else None
            fallback_id = inferred if inferred in fallback_catalog() else inferred if inferred in ('bullets','cards','process','comparison','metrics') else None
            assessment=content.get('layout_assessment') if isinstance(content.get('layout_assessment'),dict) else {}
            wants_free=assessment.get('skill_suitable') is False and isinstance(content.get('free_layout'),dict)
            if wants_free and not str(assessment.get('reason','')).strip():
                raise ValueError(f'第{index}页使用自由编排须说明技能排版不适用的原因')
            mode='free_composition' if wants_free else 'guided_composition'
            chosen.append({'page':index,'purpose':p['purpose'],'evidence':p.get('evidence'),
                           'selection_mode':mode,'selection_label':'自由编排' if wants_free else '技能排版','layout_id':None,
                           'fallback_layout_id':None if wants_free else fallback_id,
                           'candidate_ids':[],'trial_results':[],
                           'reason_code':'SKILL_LAYOUT_INADEQUATE' if wants_free else 'NO_ELIGIBLE_TEMPLATE',
                           'layout_assessment':assessment if wants_free else None,
                           'rejected_reasons':dict(rejected),
                           'theme':p.get('theme',request.get('theme')),'candidate_count':0,
                           'style_family':p.get('style_family',request.get('style_family')),
                           'source_stamp':None,'manual_review_required':True})
            chosen[-1]['request_normalization']=normalization
            continue
        scored=[]
        for e in candidates:
            fam=e.get('family_id',e['id']);penalty=layout_usage[e['id']]*5+family_usage[fam]*2
            if chosen and chosen[-1]['layout_id']==e['id']:penalty+=20
            if chosen and chosen[-1].get('family_id')==fam:penalty+=10
            if len(chosen)>1 and chosen[-2].get('family_id')==fam:penalty+=4
            impact=0
            if p.get('role')=='cover': impact={'high':3,'medium-high':2,'medium':1}.get(e.get('visual_impact'),0)
            exact_role=0 if not p.get('role') or e.get('role')==p['role'] else 1
            relation=p.get('information_relation')
            ordinary=(e.get('matching_contract') or {}).get('policy')=='structural'
            exact_relation=0 if ordinary or not relation or relation==e.get('information_relation') or relation in e.get('relation_aliases',[]) else 1
            fit=0 if ordinary else semantic_fit(p,e)
            requested_count=need.get('item_count')
            _,native_count=count_profile(e,root) if requested_count is not None else ([],None)
            count_fit=1 if requested_count is not None and requested_count==native_count else 0
            gap=binding_gap(e,p,root,p.get('theme',request.get('theme')))
            capacity_check=preflight(root,e,content,p.get('title'),p.get('theme',request.get('theme')))
            hard_count=len(capacity_check['hard_issues'])
            warning_count=len(capacity_check['advisory'])
            margin=capacity_check['capacity_margin'] if capacity_check['capacity_margin'] is not None else -1
            viable=0 if gap==0 and hard_count==0 else 1
            scored.append((viable,gap,hard_count,warning_count,-margin,exact_relation,exact_role,
                           penalty-fit*2-count_fit,-impact,rng.random(),fit,count_fit,e,capacity_check))
        scored.sort(key=lambda row:row[:10]);best=scored[0];e=best[12];fam=e.get('family_id',e['id'])
        candidate_summaries=[]
        for row in scored[:12]:
            candidate=row[12]
            binding_rel=(candidate.get('red_bindings') if p.get('theme',request.get('theme'))=='red'
                         and candidate.get('red_bindings') else candidate['bindings'])
            binding_fields=json.loads((root/binding_rel).read_text(encoding='utf-8-sig'))['fields']
            candidate_summaries.append({
                'layout_id':candidate['id'],
                'structure_type':(candidate.get('matching_contract') or {}).get('structure_type'),
                'verified_counts':count_profile(candidate,root)[0],
                'field_roles':sorted({field.get('semantic_role') for field in binding_fields
                                      if field.get('semantic_role') and field.get('semantic_role')
                                      not in ('brand_locked','decoration_locked')}),
                'required_field_count':len((candidate.get('matching_contract') or {}).get('required_binding_paths',[])),
                'meaning_policy':(candidate.get('matching_contract') or {}).get('policy',candidate.get('matching_policy')),
                'capacity':candidate.get('capacity'),
                'media_status':candidate.get('media_status'),
                'classification_status':candidate.get('classification_status'),
                'unmapped_binding_fields':row[1],
                'field_status':'ready' if row[1]==0 else 'awaiting_mapping',
                'capacity_preflight':row[13],
                'source_preview':candidate.get('preview')})
        layout_usage[e['id']]+=1;family_usage[fam]+=1
        if p.get('role')=='section' and section_layout_id is None:
            section_layout_id=e['id']
        trial_limit=request.get('max_template_trials',6)
        if type(trial_limit) is not int or not 1<=trial_limit<=8:
            raise ValueError('max_template_trials须为1至8的整数')
        chosen.append({'page':index,'purpose':p['purpose'],'evidence':p.get('evidence'),
                        'selection_mode':'source_template','selection_label':'知识库模板','candidate_ids':[e['id']] if p.get('role')=='section' else [row[12]['id'] for row in scored[:trial_limit]],
                       'candidate_summaries':candidate_summaries,
                       'field_ready_candidate_count':sum(row[1]==0 for row in scored),
                       'trial_results':[],'reason_code':None,'source_stamp':None,
                       'layout_id':e['id'],'family_id':fam,'source_mapping':e.get('source_mapping'),
                       'matched_role':e.get('role'),'matched_relation':e.get('information_relation'),
                       'canonical_relation':e.get('canonical_relation'),
                       'fit_signals':{'label_overlap':best[10],'native_count':bool(best[11]),
                                      'unmapped_binding_fields':best[1],
                                      'capacity_status':best[13]['status'],
                                      'capacity_margin':best[13]['capacity_margin']},
                       'style_family':e.get('style_family') or 'legacy-blue-red',
                       'theme':p.get('theme',request.get('theme')),'candidate_count':len(candidates),
                       'selection_reason':'指定组件' if p.get('layout_id') else '按主题、结构、字段完整性、容量风险与重复度排序；普通组件不按原稿业务标签排序',
                       'diversity_gap':family_usage[fam]>1 and all(family_usage[x.get('family_id',x['id'])]>0 for x in candidates),
                       'classification_status':e.get('classification_status'),
                       'manual_review_required':e.get('classification_status')!='verified' or e.get('status')!='approved'})
        chosen[-1]['request_normalization']=normalization
    summary={label:sum(row['selection_label']==label for row in chosen)
             for label in ('知识库模板','技能排版','自由编排')}
    return {'schema_version':'1.0','library_version':catalog['version'],'seed':seed,
            'status':'planned_not_filled','selection_summary':summary,'pages':chosen}

def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path);p.add_argument('--request',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error('输出文件已存在')
    try:
        result=resolve(a.library or get_library(),json.loads(a.request.read_text(encoding='utf-8-sig')))
        a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'pages':len(result['pages']),'seed':result['seed'],'out':str(a.out)},ensure_ascii=False))
    except (ValueError,KeyError,FileNotFoundError) as exc:p.exit(2,str(exc)+'\n')
if __name__=='__main__':main()
