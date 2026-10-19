"""Render verbatim Chinese content as one consistent 3:4 series."""
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import sys
from workflow_common import content_digest, work_key
from reorganization import check_reorganization, card_sources
from disclaimer import decision, added_note, footer_parts

TEMPLATES = {
    "editorial-blue": {"bg": "#f5f9ff", "ink": "#102c50", "accent": "#2375bd", "panel": "#ffffff", "radius": "18px", "border": "1px solid #aed0ef", "font": "sans-serif"},
    "paper-plum": {"bg": "#fff7ee", "ink": "#43233b", "accent": "#8d245c", "panel": "#fffdfa", "radius": "4px", "border": "1px solid #d8b2c6", "font": "sans-serif"},
    "sage-dossier": {"bg": "#eff4e9", "ink": "#143a26", "accent": "#315e41", "panel": "#fcfdf6", "radius": "0px", "border": "2px solid #527056", "font": "serif"},
    "warm-magazine": {"bg": "#fff8e8", "ink": "#43301d", "accent": "#b74b16", "panel": "#ffffff", "radius": "24px", "border": "2px solid #e6ae67", "font": "sans-serif"},
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def locked_text(card):
    text = [card["title"], card["subtitle"]]
    for block in card["blocks"]:
        text.append(block["heading"])
        for field in block.get("fields", []):
            text.extend((field["label"], field["text"]))
    footer, note = footer_parts(card)
    return text + [footer, note]


def local_asset(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("本地图像路径越界或文件不存在：" + value)
    return path


def validate(content, manifest, source_root):
    if manifest.get("complete") is not True or type(manifest.get("expected_count")) is not int or manifest["expected_count"] < 1:
        raise ValueError("源图完整性尚未通过，禁止排版")
    images = manifest.get("images", [])
    if len(images) != manifest["expected_count"] or manifest.get("errors"):
        raise ValueError("manifest源图数量不完整")
    if len({image.get("file") for image in images}) != len(images):
        raise ValueError("源图文件名重复")
    for index, image in enumerate(images, 1):
        if image.get("index") != index:
            raise ValueError("manifest原始页码不连续")
        source = local_asset(source_root, image["file"])
        if hashlib.sha256(source.read_bytes()).hexdigest() != image.get("sha256"):
            raise ValueError("源图哈希变化")
    if content.get("transcription_reviewed") is not True:
        raise ValueError("必须先逐张看图核对完整文字，再设置transcription_reviewed=true")
    if content.get("source_url") != manifest.get("source_url"):
        raise ValueError("content来源URL与manifest不一致")
    cards = content.get("cards", [])
    selected = content.get("selected_indices", list(range(1, len(images) + 1)))
    if (not isinstance(selected, list) or not selected
            or any(type(i) is not int or i < 1 or i > len(images) for i in selected)
            or selected != sorted(set(selected))):
        raise ValueError("selected_indices必须是原图范围内、升序且不重复的整数页码")
    mode = content.get('mode', 'faithful')
    if mode not in ('faithful', 'smart'):
        raise ValueError('mode仅支持faithful或smart')
    if mode == 'smart':
        check_reorganization(content, selected)
    elif len(cards) != len(selected):
        raise ValueError("二创图必须与选定源图一一对应，不能缺图或混入未选图片")
    for position, card in enumerate(cards):
        decision(card)
        if mode == 'faithful':
            image = images[selected[position] - 1]
            if card.get("source_image") != image.get("file"):
                raise ValueError("源图对应或顺序不一致")
        for key in ("title", "subtitle", "footer"):
            if not isinstance(card.get(key), str):
                raise ValueError("每张卡片需提供字符串字段：" + key)
        if not isinstance(card.get("blocks"), list) or not card["blocks"]:
            raise ValueError("正文不能为空")
        for block in card["blocks"]:
            if not isinstance(block.get("heading"), str):
                raise ValueError("正文块heading必须是字符串")
            if not block.get("fields") and not block.get("image"):
                raise ValueError("正文块没有内容")
            for field in block.get("fields", []):
                if not isinstance(field.get("label"), str) or not isinstance(field.get("text"), str) or not field["text"].strip():
                    raise ValueError("字段label/text不合法或正文为空")
            if block.get("image"):
                local_asset(source_root, block["image"])
    return cards


def choose_style(content, output, history_path, requested=None):
    digest = content_digest(content)
    key = work_key(content["source_url"])
    local = output / "style.json"
    previous = read_json(local) if local.exists() else None
    history = read_json(history_path) if history_path.exists() else {"last_template": None, "jobs": []}
    bound = history.get("works", {}).get(key)
    if bound:
        if requested and requested != bound["template"]:
            raise ValueError("同一作品已锁定风格；新模板需使用新的独立history明确开启设计版本")
        template = bound["template"]
    elif requested:
        template = requested
    elif previous and previous.get("work_key", key) == key and previous.get("content_sha256") == digest:
        template = previous["template"]
    else:
        names = list(TEMPLATES)
        last = history.get("last_template")
        template = names[(names.index(last) + 1) % len(names)] if last in names else names[0]
    return {"template": template, "work_key": key, "content_sha256": digest, "width": 1080, "height": 1440}, history


def verbatim(value, tag="span", cls=""):
    # Explicitly mark each original text atom, including empty optional strings.
    return f'<{tag} class="verbatim {cls}">{html.escape(value)}</{tag}>'


def disclaimer_style(style):
    t = TEMPLATES[style['template']]
    return {'font_family': 'CustomerFont,"Microsoft YaHei","Noto Sans CJK SC","PingFang SC",' + t['font'],
            'font_size_px_at_1080': 22, 'font_weight': 400, 'color': t['ink'],
            'alignment': 'right', 'bottom_margin_px_at_1080': 36, 'line_height': 1.4}


def card_html(card, style, source_root, font_file=None):
    t = TEMPLATES[style["template"]]
    font_face = ""
    if font_file:
        font_face = '@font-face{font-family:CustomerFont;src:url(data:font/ttf;base64,' + base64.b64encode(Path(font_file).read_bytes()).decode() + ')}'
    family = 'CustomerFont,"Microsoft YaHei","Noto Sans CJK SC","PingFang SC",' + t["font"]
    panels = []
    for block in card["blocks"]:
        fields = []
        for field in block.get("fields", []):
            label = verbatim(field["label"], cls="label")
            separator = "：" if field["label"] else ""
            fields.append('<div class="field">' + label + separator + verbatim(field["text"]) + '</div>')
        asset = ""
        if block.get("image"):
            data = base64.b64encode(local_asset(source_root, block["image"]).read_bytes()).decode()
            from PIL import Image
            with Image.open(local_asset(source_root, block["image"])) as image:
                mime = Image.MIME.get(image.format, "image/png")
            asset = f'<img class="insert" src="data:{mime};base64,{data}">'
        panels.append('<section class="panel">' + verbatim(block["heading"], "h2") + '<div class="details">' + ''.join(fields) + asset + '</div></section>')
    css = f"""{font_face}
*{{box-sizing:border-box}} html,body{{margin:0;width:1080px;height:1440px}}
body{{font-family:{family};color:{t['ink']};background:{t['bg']}}} .card{{width:1080px;height:1440px;padding:36px;display:flex;flex-direction:column;gap:18px;overflow:hidden}}
header{{flex-shrink:0;border-bottom:3px solid {t['accent']};padding-bottom:14px}} h1{{margin:0;font-size:68px;line-height:1.15;letter-spacing:2px;font-weight:900}} .subtitle{{font-size:30px;margin-top:10px;display:block;line-height:1.25}}
main{{flex:1;min-height:0;display:flex;flex-direction:column;gap:16px}} .panel{{flex:1;min-height:0;background:{t['panel']};border:{t['border']};border-radius:{t['radius']};display:flex;flex-direction:column;overflow:hidden}}
h2{{margin:0;padding:9px 18px;font-size:calc(var(--body-size,26px) * 1.35);line-height:1.15;background:{t['accent']};color:white;font-weight:800}}
.details{{padding:12px 18px;flex:1;min-height:0;font-size:var(--body-size,26px);line-height:1.42}} .field{{margin-bottom:8px;white-space:pre-wrap;overflow-wrap:anywhere}} .field:last-child{{margin-bottom:0}} .label{{font-weight:800}} .insert{{max-width:100%;max-height:150px;object-fit:contain;display:block;margin:5px auto}}
footer{{flex-shrink:0;font-size:27px;font-weight:800;border-top:2px solid {t['accent']};padding-top:12px;line-height:1.3;white-space:pre-wrap}}
.verbatim{{white-space:pre-wrap}}
.disclaimer{{flex-shrink:0;font-size:22px;line-height:1.4;color:{t['ink']};font-weight:400;text-align:right;margin-top:0;white-space:nowrap}}
"""
    if style["template"] == "paper-plum":
        css += "header{border-bottom-style:double;border-bottom-width:6px}.panel{flex-direction:row}h2{width:200px;flex-shrink:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:18px}.details{min-width:0}"
    elif style["template"] == "sage-dossier":
        css += f".panel{{border-left:10px solid {t['accent']}}}h2{{background:transparent;color:{t['ink']};border-bottom:1px dashed {t['accent']};padding:8px 18px}}header{{border-bottom-style:dashed}}"
    elif style["template"] == "warm-magazine":
        css += "header{text-align:center}h1{font-size:74px}h2{border-radius:0 24px 24px 0;width:fit-content;min-width:260px;padding-right:36px}footer{text-align:center}"
    footer, note = footer_parts(card)
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>' + css + '</style><body><article class="card"><header>' + verbatim(card['title'], 'h1') + verbatim(card['subtitle'], cls='subtitle') + '</header><main>' + ''.join(panels) + '</main>' + verbatim(footer, 'footer') + verbatim(note, 'aside', 'disclaimer') + '</article></body></html>'


OVERFLOW_JS = """() => [...document.querySelectorAll('.card,header,main,.panel,.details,footer,.field,.disclaimer')].filter(e => e.scrollHeight > e.clientHeight + 2 || e.scrollWidth > e.clientWidth + 2).map(e => e.className || e.tagName)"""


def render(args):
    from playwright.sync_api import sync_playwright
    from PIL import Image
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.glob("*.png")) or any(output.glob("*.html")):
        (output / "review.json").write_text(json.dumps({"passed": False, "error": "已有图片/HTML，使用新的输出目录以隔离旧文件"}, ensure_ascii=False), encoding="utf-8")
        raise ValueError("已有图片/HTML，使用新的输出目录以隔离旧文件")
    # Invalidate an earlier success report before checking a revised input.
    (output / "review.json").write_text(json.dumps({"passed": False, "status": "validating"}), encoding="utf-8")
    try:
        content = read_json(args.content)
        manifest = read_json(args.manifest)
        source_root = Path(args.manifest).resolve().parent
        cards = validate(content, manifest, source_root)
    except Exception as error:
        (output / "review.json").write_text(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False), encoding="utf-8")
        raise
    history_path = Path(args.history).expanduser().resolve()
    style, history = choose_style(content, output, history_path, args.template)
    htmls = [card_html(card, style, source_root, args.font_file) for card in cards]
    # One font size for the entire series, chosen against its densest page.
    report = {"passed": False, "template": style["template"], "source_transcription_reviewed": True,
              "work_key": style["work_key"], "content_sha256": style["content_sha256"], "cards": [],
              "disclaimer_style": disclaimer_style(style)}
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as chromium_error:
                # Reuse installed Google Chrome when Playwright's bundled
                # Chromium is absent (common in managed desktop installs).
                try:
                    browser = p.chromium.launch(channel="chrome", headless=True)
                except Exception:
                    raise chromium_error
            try:
                pages = []
                for markup in htmls:
                    page = browser.new_page(viewport={"width": 1080, "height": 1440}, device_scale_factor=1)
                    page.set_content(markup, wait_until="load")
                    page.evaluate("() => document.fonts.ready")
                    pages.append(page)
                size = None
                for candidate in range(28, 17, -1):
                    for page in pages:
                        page.evaluate("s => document.documentElement.style.setProperty('--body-size',s+'px')", candidate)
                    if all(not page.evaluate(OVERFLOW_JS) for page in pages):
                        size = candidate
                        break
                if size is None:
                    raise ValueError("完整内容在最低字号仍溢出；需确认分页方案，禁止删字")
                style["body_font_size"] = size
                for index, (page, card, markup) in enumerate(zip(pages, cards, htmls), 1):
                    actual = page.locator(".verbatim").all_text_contents()
                    if actual != locked_text(card):
                        raise ValueError(f"第{index}张DOM文字与冻结原文不一致")
                    png = output / f"{index:02d}.png"
                    page.screenshot(path=str(png))
                    with Image.open(png) as image:
                        dimensions = image.size
                    if dimensions != (1080, 1440):
                        raise ValueError("输出尺寸不符合3:4")
                    markup = markup.replace('var(--body-size,26px)', f'{size}px')
                    (output / f"{index:02d}.html").write_text(markup, encoding="utf-8")
                    sources = card_sources(content, manifest)[index-1]
                    record = {"file": png.name, "source_indices": sources, "width": dimensions[0], "height": dimensions[1],
                                            "sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
                                            "disclaimer": added_note(card),
                                            "disclaimer_decision": decision(card),
                                            "disclaimer_style": report['disclaimer_style'] if footer_parts(card)[1] else None,
                                            "text_match": True, "overflow": False}
                    if content.get('mode', 'faithful') != 'smart':
                        record.update(source_index=sources[0], source_image=card['source_image'])
                    report["cards"].append(record)
            finally:
                browser.close()
        report["passed"] = True
        (output / "style.json").write_text(json.dumps(style, ensure_ascii=False, indent=2), encoding="utf-8")
        history["last_template"] = style["template"]
        history.setdefault("works", {}).setdefault(style["work_key"], {})["template"] = style["template"]
        history["jobs"].append({"content_sha256": style["content_sha256"], "template": style["template"]})
        history["jobs"] = history["jobs"][-100:]
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        (output / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "cards": len(cards), "template": style["template"],
                      "body_font_size": size, "output": str(output)}, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "render"):
        command = commands.add_parser(name)
        command.add_argument("--content", required=True)
        command.add_argument("--manifest", required=True)
        if name == "render":
            command.add_argument("--output", required=True)
            command.add_argument("--template", choices=list(TEMPLATES))
            command.add_argument("--history", default=str(Path.home() / ".social-image-remix/style-history.json"))
            command.add_argument("--font-file", help="本地中文字体文件，嵌入HTML以确保跨机器字形")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            cards = validate(read_json(args.content), read_json(args.manifest), Path(args.manifest).resolve().parent)
            print(json.dumps({"passed": True, "cards": len(cards)}, ensure_ascii=False))
            return 0
        return render(args)
    except Exception as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
