"""Read current-work images through the customer's browser. Never export cookies."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse
import uuid

PLATFORMS = {
    "douyin": ("douyin.com", "iesdouyin.com"),
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com", "xhslink.cn"),
    "kuaishou": ("kuaishou.com", "chenzhongtech.com"),
}
CDNS = ("douyinpic.com", "byteimg.com", "douyincdn.com", "xhscdn.com",
        "xiaohongshu.com", "kwimgs.com", "kwaicdn.com", "ksapisrv.com", "gifshow.com")


def host_matches(host, suffix):
    return host == suffix or host.endswith("." + suffix)


def extract_url(text):
    match = re.search(r"https?://[^\s<>\"']+", text)
    if not match:
        raise ValueError("没有找到HTTP分享链接")
    url = match.group(0).rstrip("。，；）)]}")
    host = (urlparse(url).hostname or "").lower()
    for platform, domains in PLATFORMS.items():
        if any(host_matches(host, d) for d in domains):
            return url, platform
    raise ValueError("仅接受抖音、小红书、快手作品链接")


def opencli_command():
    override = os.environ.get("SOCIAL_REMIX_OPENCLI")
    candidate = override or shutil.which("opencli") or shutil.which("opencli.cmd") or shutil.which("opencli.ps1")
    if not candidate:
        raise RuntimeError("缺少OpenCLI；安装@jackwener/opencli并连接Browser Bridge扩展")
    path = Path(candidate)
    if os.name == "nt":
        # npm shims live beside node_modules. Avoid cmd.exe/string interpolation.
        main = path.parent / "node_modules/@jackwener/opencli/dist/src/main.js"
        node = path.parent / "node.exe"
        if main.exists():
            executable = str(node) if node.exists() else shutil.which("node")
            if not executable:
                raise RuntimeError("缺少Node.js")
            return [executable, str(main)]
        if path.suffix.lower() == ".ps1":
            return [shutil.which("pwsh") or "powershell", "-NoProfile", "-File", str(path)]
        raise RuntimeError("找不到OpenCLI Node入口；将SOCIAL_REMIX_OPENCLI设为npm的opencli.ps1路径")
    return [str(path)]


def run_browser(args, timeout=90):
    proc = subprocess.run(opencli_command() + args, capture_output=True, timeout=timeout,
                          encoding="utf-8", errors="replace")
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:1500])
    return proc.stdout


def decode_json(output):
    # OpenCLI may append update notices. Accept a JSON result without those notices.
    decoder = json.JSONDecoder()
    for line in output.splitlines():
        line = line.strip()
        if line.startswith(("{", "[")):
            try:
                value, _ = decoder.raw_decode(output[output.index(line):])
                return value
            except (json.JSONDecodeError, ValueError):
                continue
    raise ValueError("浏览器没有返回可解析的JSON")


def dom_query(platform, selector):
    # Selector is serialized as JS data, never interpolated into executable syntax.
    options = json.dumps({"platform": platform, "selector": selector}, ensure_ascii=False)
    return """(() => {
 const opt = OPTIONS;
 let nodes;
 if (opt.selector) nodes = Array.from(document.querySelectorAll(opt.selector));
 else if (opt.platform === 'douyin') nodes = Array.from(document.images).filter(i => {
   try { return new URL(i.currentSrc || i.src).searchParams.get('sc') === 'image'; }
   catch { return false; }
 });
 else throw new Error('此平台需要当前作品图片的CSS选择器');
 const images = [], seen = new Set();
 for (const node of nodes) {
   if (!(node instanceof HTMLImageElement)) continue;
   const url = node.currentSrc || node.src;
   if (!url.startsWith('https://') || node.naturalWidth < 300 || node.naturalHeight < 300) continue;
   const key = new URL(url).pathname;
   if (!seen.has(key)) { seen.add(key); images.push({url, width:node.naturalWidth, height:node.naturalHeight}); }
 }
 const counts = Array.from(document.querySelectorAll('span,div')).filter(e =>
   e.children.length === 0 && e.getBoundingClientRect().width > 0)
   .map(e => e.textContent.trim()).filter(t => /^\\d+\\s*\\/\\s*\\d+$/.test(t));
 const totals = [...new Set(counts.map(t => Number(t.split('/')[1])))];
 return JSON.stringify({source_url:location.href, title:document.title,
   expected_count:totals.length === 1 ? totals[0] : null, images});
})()""".replace("OPTIONS", options)


def download_image(url, path):
    import requests
    from PIL import Image
    host = (urlparse(url).hostname or "").lower()
    if urlparse(url).scheme != "https" or not any(host_matches(host, d) for d in CDNS):
        raise ValueError("图片不是已支持的平台HTTPS CDN地址：" + host)
    with requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=30) as response:
        response.raise_for_status()
        final_host = (urlparse(response.url).hostname or "").lower()
        if not any(host_matches(final_host, d) for d in CDNS):
            raise ValueError("图片跳转到不支持的CDN")
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > 40 * 1024 * 1024:
                raise ValueError("单张图片超过40MB")
    path.write_bytes(data)
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(image.format)
            if not extension:
                raise ValueError("仅支持JPEG、PNG、WebP静态源图")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    destination = path.with_suffix(extension)
    path.rename(destination)
    return {"file": destination.name, "width": width, "height": height,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def doctor():
    results = {name: importlib.util.find_spec(name) is not None
               for name in ("requests", "PIL", "playwright")}
    try:
        results["browser_bridge"] = run_browser(["doctor"], timeout=40).strip()
        results["opencli"] = True
    except Exception as error:
        results["opencli"] = False
        results["browser_error"] = str(error)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(results[n] for n in ("requests", "PIL", "playwright", "opencli")) else 2


def extract(args):
    url, platform = extract_url(args.url)
    if platform != "douyin" and not args.selector:
        raise ValueError("小红书/快手v0.1需要--selector定位当前作品图片；参见references/browser.md")
    root = Path(args.output).resolve()
    if (root / "manifest.json").exists():
        raise ValueError("输出目录已有manifest；用新任务目录，避免覆盖源图")
    root.mkdir(parents=True, exist_ok=True)
    session = args.session or "social-remix-" + uuid.uuid4().hex[:10]
    opened = False
    try:
        if not args.session:
            run_browser(["browser", session, "open", url, "--window", "background"])
            opened = True
        # With --session, use an already-open, manually advanced gallery.
        snapshot = None
        for attempt in range(6):
            snapshot = decode_json(run_browser(["browser", session, "eval", dom_query(platform, args.selector)]))
            if snapshot.get("images"):
                break
            time.sleep(1.5)
        resolved, resolved_platform = extract_url(snapshot["source_url"])
        if resolved_platform != platform:
            raise ValueError("浏览器最终平台与输入不一致")
        # Existing sessions must correspond to the requested work, not a different tab.
        if args.session:
            supplied_id = re.search(r"/(?:note|video|explore|short-video)/([^/?]+)", url)
            resolved_id = re.search(r"/(?:note|video|explore|short-video)/([^/?]+)", resolved)
            if not supplied_id or not resolved_id or supplied_id[1] != resolved_id[1]:
                raise ValueError("复用会话时请传与当前作品一致的完整作品URL")
        expected = args.expected_count or snapshot.get("expected_count")
        manifest = {"version": 1, "platform": platform, "input_url": url, "source_url": resolved,
                    "expected_count": expected, "complete": False, "images": [], "errors": []}
        for index, item in enumerate(snapshot.get("images", []), 1):
            try:
                record = download_image(item["url"], root / f"{index:02d}.image")
                record.update(index=index, url=item["url"])
                manifest["images"].append(record)
            except Exception as error:
                # No raw URL or credentials in public diagnostics.
                manifest["errors"].append({"index": index, "reason": type(error).__name__})
        manifest["complete"] = bool(expected and len(manifest["images"]) == expected and not manifest["errors"])
        (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"manifest": str(root / "manifest.json"), "platform": platform,
                          "downloaded": len(manifest["images"]), "expected": expected,
                          "complete": manifest["complete"], "errors": manifest["errors"]}, ensure_ascii=False))
        return 0 if manifest["complete"] else 2
    finally:
        if opened:
            try:
                run_browser(["browser", session, "close"], timeout=20)
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    command = commands.add_parser("extract")
    command.add_argument("--url", required=True)
    command.add_argument("--output", required=True)
    command.add_argument("--selector")
    command.add_argument("--expected-count", type=int)
    command.add_argument("--session", help="复用已定位并翻页的会话；此时--url必须是完整作品URL")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            return doctor()
        if args.expected_count is not None and args.expected_count < 1:
            raise ValueError("expected-count必须大于0")
        return extract(args)
    except Exception as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
