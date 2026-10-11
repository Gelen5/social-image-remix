"""Shared identities and counting rules; never infer semantic correctness."""
import hashlib
import json
import re
from urllib.parse import urlparse


def content_digest(content):
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def work_key(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    patterns = (("douyin.com", "douyin"), ("iesdouyin.com", "douyin"),
                ("kuaishou.com", "kuaishou"), ("chenzhongtech.com", "kuaishou"),
                ("xiaohongshu.com", "xiaohongshu"))
    match = re.search(r"/(?:note|video|explore|short-video|photo|discovery/item)/([^/?]+)", parsed.path)
    if match:
        for domain, platform in patterns:
            if host == domain or host.endswith("." + domain):
                return platform + ":" + match[1]
    # Resolved work URL preferred; remove tracking query/fragment.
    return host + parsed.path.rstrip("/")


def count_text(text):
    """Non-whitespace Unicode characters, including punctuation, digits and Latin."""
    return sum(not c.isspace() for c in text)
