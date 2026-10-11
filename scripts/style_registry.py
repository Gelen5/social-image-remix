"""Reserve one design per resolved work for imagegen and deterministic rendering."""
import argparse
import json
from pathlib import Path
from render_cards import choose_style
from workflow_common import work_key


def reserve(source_url, history_path, design_file=None):
    history_path = Path(history_path).expanduser()
    style, history = choose_style({"source_url": source_url}, Path('__no_task_output__'), history_path)
    key = work_key(source_url)
    record = history.setdefault('works', {}).get(key)
    if record is None:
        if design_file is None:
            raise ValueError('首次生图需--design-file提供整组设计规范JSON')
        design = json.loads(Path(design_file).read_text(encoding='utf-8-sig'))
        if not isinstance(design, dict) or not design:
            raise ValueError('设计规范必须是非空JSON对象')
        record = {'template': style['template'], 'design': design}
        history['works'][key] = record
        history['last_template'] = style['template']
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')
    if not record.get('design'):
        raise ValueError('该作品只有备用模板绑定；使用独立history建立生图设计规范')
    return dict(record, work_key=key)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-url', required=True)
    p.add_argument('--history', default=str(Path.home()/'.social-image-remix/style-history.json'))
    p.add_argument('--design-file')
    a = p.parse_args()
    print(json.dumps(reserve(a.source_url, a.history, a.design_file), ensure_ascii=False, indent=2))
