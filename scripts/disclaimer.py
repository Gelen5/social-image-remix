"""Validate the host's per-final-image semantic decision; never infer by keywords."""
from workflow_common import IMAGE_DISCLAIMER


def decision(card):
    value = card.get('disclaimer_decision')
    if not isinstance(value, dict):
        raise ValueError('每张最终图片必须记录脚注语义判断disclaimer_decision')
    category = value.get('classification')
    if category not in ('recruitment', 'general', 'uncertain'):
        raise ValueError('脚注classification须为recruitment/general/uncertain')
    if type(value.get('required')) is not bool or value['required'] != (category != 'general'):
        raise ValueError('脚注判断矛盾：招聘推荐或不确定时必须添加，通用内容不新增')
    if not isinstance(value.get('reason'), str) or not value['reason'].strip():
        raise ValueError('脚注判断需提供语义理由')
    evidence = value.get('evidence')
    if not isinstance(evidence, list) or not evidence or any(not isinstance(t, str) or not t.strip() for t in evidence):
        raise ValueError('脚注判断需引用本张保留内容作为证据')
    return value


def added_note(card):
    return IMAGE_DISCLAIMER if decision(card)['required'] else None


def footer_parts(card):
    note = added_note(card)
    footer = card['footer']
    # Preserve a source disclaimer even when no new disclaimer is required.
    if note and footer.strip() == note:
        footer = ''
    return footer, note or ''
