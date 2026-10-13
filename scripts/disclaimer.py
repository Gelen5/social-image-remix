"""Validate the host's per-final-image semantic decision; never infer by keywords."""
from workflow_common import IMAGE_DISCLAIMER
import math


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
    if footer.strip() == IMAGE_DISCLAIMER:
        footer, note = '', IMAGE_DISCLAIMER
    return footer, note or ''


def check_styles(report, cards):
    visible = [(entry, card) for entry, card in zip(report['cards'], cards) if footer_parts(card)[1]]
    if not visible:
        return
    style = report.get('disclaimer_style')
    if not isinstance(style, dict):
        raise ValueError('整组提示语需锁定disclaimer_style')
    for key in ('font_family', 'color', 'alignment'):
        if not isinstance(style.get(key), str) or not style[key].strip():
            raise ValueError('提示语样式缺少字体、颜色或对齐方式')
    for key in ('font_size_px_at_1080', 'font_weight', 'bottom_margin_px_at_1080', 'line_height'):
        value = style.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError('提示语样式数值缺失或不合法')
    for entry, card in visible:
        if entry.get('disclaimer_style') != style:
            raise ValueError('各图片提示语字体、字号、字重及位置必须与整组锁定样式一致')
