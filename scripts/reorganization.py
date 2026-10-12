"""Validate smart-mode scope and declared information coverage, not semantics."""


def card_sources(content, manifest):
    smart = content.get('mode', 'faithful') == 'smart'
    if smart:
        return [card['source_indices'] for card in content['cards']]
    lookup = {image['file']:image['index'] for image in manifest['images']}
    return [[lookup[card['source_image']]] for card in content['cards']]


def check_reorganization(content, selected):
    plan = content.get('reorganization')
    if not isinstance(plan, dict) or plan.get('reviewed') is not True:
        raise ValueError('智能重组需实际完成信息覆盖与语义复核')
    alternatives = plan.get('alternatives', [])
    if (not isinstance(alternatives, list) or len(alternatives) < 2
            or any(not isinstance(a, dict) or not isinstance(a.get('id'), str) or not a['id']
                   or type(a.get('page_count')) is not int or a['page_count'] < 1
                   or not isinstance(a.get('reason'), str) or not a['reason'].strip() for a in alternatives)):
        raise ValueError('需比较至少两个有页数和具体理由的重组方案')
    if len({a['id'] for a in alternatives}) != len(alternatives):
        raise ValueError('方案ID重复')
    chosen = [a for a in alternatives if a['id'] == plan.get('chosen')]
    if len(chosen) != 1 or chosen[0]['page_count'] != len(content['cards']):
        raise ValueError('实际输出页数与选定方案不一致')
    if not isinstance(plan.get('reason'), str) or not plan['reason'].strip():
        raise ValueError('缺少方案选择理由')
    if not content['cards']:
        raise ValueError('智能重组不能没有输出图片')
    facts = content.get('source_facts')
    if not isinstance(facts, list) or not facts:
        raise ValueError('需先冻结所选原图完整信息清单source_facts')
    lookup = {}
    covered_pages = set()
    for fact in facts:
        if not isinstance(fact, dict) or not isinstance(fact.get('id'), str) or not fact['id'] or fact['id'] in lookup:
            raise ValueError('信息清单ID缺失或重复')
        pages = fact.get('source_indices')
        if (not isinstance(pages, list) or not pages or any(type(i) is not int or i not in selected for i in pages)
                or pages != sorted(set(pages))):
            raise ValueError('信息清单引用未选图片或错误页码')
        if not isinstance(fact.get('text'), str) or not fact['text'].strip():
            raise ValueError('信息清单原文不能为空')
        kind, action = fact.get('kind'), fact.get('action')
        if kind not in ('fact', 'promotion', 'filler') or action not in ('retained', 'merged_duplicate', 'removed'):
            raise ValueError('信息类型或处理方式不合法')
        if action == 'removed' and kind == 'fact':
            raise ValueError('不能删除独有实质信息来压缩页数')
        if action != 'retained' and (not isinstance(fact.get('reason'), str) or not fact['reason'].strip()):
            raise ValueError('删除或合并必须记录理由')
        lookup[fact['id']] = fact
        covered_pages.update(pages)
    if covered_pages != set(selected):
        raise ValueError('信息清单未覆盖全部选中原图')
    retained = {fid for fid, f in lookup.items() if f['action'] == 'retained'}
    for f in facts:
        if f['action'] == 'merged_duplicate':
            target = lookup.get(f.get('duplicate_of'))
            if not target or target['id'] not in retained or target['kind'] != f['kind']:
                raise ValueError('重复合并需指向同类已保留信息，不能循环或丢失')
    used = set()
    for card in content['cards']:
        pages = card.get('source_indices')
        if (not isinstance(pages, list) or not pages or pages != sorted(set(pages))
                or any(type(i) is not int or i not in selected for i in pages)):
            raise ValueError('成品来源页码必须在选定范围内')
        ids = card.get('fact_ids')
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('每张成品需声明不重复的信息覆盖ID')
        for fid in ids:
            if fid not in retained or not set(lookup[fid]['source_indices']).issubset(pages):
                raise ValueError('成品覆盖ID被删除、未保留或与来源页不一致')
        used.update(ids)
    if used != retained:
        raise ValueError('成品遗漏已保留信息，禁止交付')
