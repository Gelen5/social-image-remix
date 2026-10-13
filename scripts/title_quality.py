"""Two title sets with exact lengths and version-bound host editorial reviews."""
import unicodedata


def validate_titles(caption_titles, article_titles):
    sets = {'caption': caption_titles, 'article': article_titles}
    seen = set()
    for role, values in sets.items():
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError('贴图号与文章各需3个标题')
        for title in values:
            if (not isinstance(title, str) or not title.strip() or title != title.strip()
                    or any(unicodedata.category(c) in ('Cc', 'Cf', 'Zl', 'Zp') for c in title)
                    or '  ' in title):
                raise ValueError('标题必须为非空单行，不得用空白或隐形字符凑字数')
            size = len(title)  # Count punctuation, Latin letters, digits and spaces too.
            if role == 'caption' and size != 19:
                raise ValueError('贴图号标题每条必须恰好19字，标点数字英文空格均计数')
            if role == 'article' and size > 32:
                raise ValueError('文章标题不能超过32字')
            if title in seen:
                raise ValueError('两组6个标题不能重复或整条复用')
            seen.add(title)
    return sets


def check_title_reviews(review, sets):
    expected = [(role, index, title) for role, values in sets.items()
                for index, title in enumerate(values, 1)]
    checks = review.get('title_checks')
    if not isinstance(checks, list) or len(checks) != 6:
        raise ValueError('需逐条完成两组6个标题的事实、自然度、吸引力及差异复核')
    for item, (role, index, title) in zip(checks, expected):
        if (not isinstance(item, dict) or item.get('role') != role or item.get('index') != index
                or item.get('title') != title or item.get('characters') != len(title)):
            raise ValueError('标题复核对应旧标题、错场景或错字数')
        if any(item.get(k) is not True for k in ('facts_supported', 'natural', 'appeal', 'distinct')) or item.get('issues') != []:
            raise ValueError('标题存在未解决的事实、表达、吸引力或差异问题')
        if not isinstance(item.get('notes'), str) or not item['notes'].strip():
            raise ValueError('每个标题需有实际编辑复核说明')
    if (review.get('writing_reviewed') is not True or review.get('writing_issues') != []
            or not isinstance(review.get('writing_notes'), str) or not review['writing_notes'].strip()):
        raise ValueError('配文和独立文章需实际复核自然表达、段落衔接及阅读线索')
