#!/usr/bin/env python3
"""
The Blood of Dawnwalker — editorial radar + auto-publisher.

Pipeline:
  RSS/news (Steam app 3751260, Reddit, Google/Bing News)
    -> dedupe + relevance score
    -> agy (Antigravity subscription, no API cost) / Gemini writes a Feishu brief
       + a publishable article in OUR Astro frontmatter format
    -> (optional) agy/Imagen header image, optimized to WebP
    -> commit .md (+ image) to the site repo via the GitHub Contents API
       (Cloudflare Pages auto-deploys on push)
    -> Feishu push for human review

Adapted from the outward2/themound radar template for dawnwalker.wiki.
The site is Astro (static content collections) — articles are committed straight
to src/content/news and Cloudflare builds them; there is no local clone or
build_site.py step. Secrets come from ai_editor.env (same dir). Never commit it.
"""

import base64
import calendar
import hashlib
import html
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, quote_plus, urlencode, urlparse, urlunparse

import feedparser
import requests
import yaml

try:
    import google.generativeai as genai
except Exception:  # library optional until configured
    genai = None


# --- config / env -----------------------------------------------------------
def _first_existing(*paths):
    for p in paths:
        if Path(p).exists():
            return Path(p)
    return Path(paths[0])


STATE_DIR = Path(__file__).resolve().parent
ENV_FILE = _first_existing(STATE_DIR / "ai_editor.env", "/opt/p6-dawnwalker-radar/ai_editor.env")
LAST_RUN_FILE = STATE_DIR / "ai_editor_last_run.txt"
SEEN_FILE = STATE_DIR / "ai_editor_seen.json"


def load_env_file(path):
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ENV_FILE)

DEFAULT_LOOKBACK_HOURS = int(os.getenv("AI_EDITOR_LOOKBACK_HOURS", "26"))
MAX_ITEMS_FOR_AI = int(os.getenv("AI_EDITOR_MAX_ITEMS", "35"))
MAX_SEEN_ITEMS = int(os.getenv("AI_EDITOR_MAX_SEEN", "800"))
DRY_RUN = os.getenv("AI_EDITOR_DRY_RUN", "").lower() in {"1", "true", "yes"}

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "models/gemini-3.1-pro-preview")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "angeller0908-web/p6-dawnwalker")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GITHUB_CONTENT_DIR = os.getenv("GITHUB_CONTENT_DIR", "src/content/news").strip("/")
GITHUB_GUIDES_DIR = os.getenv("GITHUB_GUIDES_DIR", "src/content/guides").strip("/")
GITHUB_AUTHOR_NAME = os.getenv("GITHUB_AUTHOR_NAME", "Dawnwalker Editorial Bot")
GITHUB_AUTHOR_EMAIL = os.getenv("GITHUB_AUTHOR_EMAIL", "bot@dawnwalker.wiki")

# Astro serves /public at the web root, so a file committed to public/images/news/x.webp
# is referenced in frontmatter as /images/news/x.webp.
GITHUB_IMAGE_DIR = os.getenv("GITHUB_IMAGE_DIR", "public/images/news").strip("/")
IMAGE_WEB_PREFIX = os.getenv("IMAGE_WEB_PREFIX", "/images/news").rstrip("/")
# "agy" -> generate via the Antigravity subscription CLI (no API cost), Imagen API fallback.
# "off" -> skip image generation entirely (articles publish text-only; the gradient
#          Banner shows instead, which is a valid state for the site).
IMAGE_MODE = os.getenv("AI_EDITOR_IMAGE_MODE", "agy").lower()
IMAGE_STYLE_SUFFIX = os.getenv(
    "IMAGE_STYLE_SUFFIX",
    "original dark-fantasy vampire RPG concept art, gothic Eastern-European valley at "
    "blood-red dawn, brooding atmosphere, distant castle silhouette, painterly digital "
    "art, cinematic volumetric lighting, no text, no watermark, no logo, no real people, "
    "do NOT depict any character or scene from any existing copyrighted game",
)

# Frontmatter keys the Astro news schema understands. Everything else is dropped
# by the sanitizer so a hallucinated key can never break the zod build validation.
ALLOWED_FRONTMATTER_KEYS = {
    "title", "description", "publishDate", "updatedDate", "author",
    "tags", "image", "imageAlt", "video", "videoTitle", "draft", "sources",
}

if GEMINI_API_KEY and genai:
    genai.configure(api_key=GEMINI_API_KEY)


# --- the game ---------------------------------------------------------------
GAME_NAME = "The Blood of Dawnwalker"
GAME_RELEASE = "2026-09-03"
STEAM_APP_ID = os.getenv("STEAM_APP_ID", "3751260")

DAWNWALKER_TERMS = [
    "blood of dawnwalker",
    "the blood of dawnwalker",
    "dawnwalker",
]
# Disambiguating context (the word "dawnwalker" alone is generic, so require a second signal).
DAWNWALKER_CONTEXT = [
    "rebel wolves", "bandai namco", "vale sangora", "coen", "vampire",
    "witcher", "narrative sandbox", "3751260", "dawnwalkergame",
]

GUIDE_SIGNALS = [
    "guide", "walkthrough", "tips", "tricks", "build", "class", "skill",
    "skill tree", "combat", "magic", "hex", "weapon", "armor", "crafting",
    "vampire", "wolf form", "day", "night", "quest", "story", "ending",
    "romance", "map", "world", "region", "preview", "hands-on", "gameplay",
    "trailer", "developer", "interview", "patch", "update", "release date",
    "price", "editions", "preorder", "pre-order", "system requirements",
    "pc requirements", "deluxe", "collector", "demo", "beta", "review",
]

SEARCH_QUERIES = [
    '"The Blood of Dawnwalker"',
    '"Blood of Dawnwalker"',
    '"The Blood of Dawnwalker" guide',
    '"The Blood of Dawnwalker" gameplay',
    '"The Blood of Dawnwalker" preview',
    '"The Blood of Dawnwalker" interview',
    '"The Blood of Dawnwalker" trailer',
    '"The Blood of Dawnwalker" release date',
    '"The Blood of Dawnwalker" editions',
    '"The Blood of Dawnwalker" preorder',
    '"The Blood of Dawnwalker" system requirements',
    '"Blood of Dawnwalker" Rebel Wolves',
]


def build_sources():
    sources = [
        {
            "name": f"Steam News - {GAME_NAME}",
            "url": f"https://store.steampowered.com/feeds/news/app/{STEAM_APP_ID}",
            "trusted": True,
        },
        {
            "name": "Reddit Search - Dawnwalker",
            "url": "https://www.reddit.com/search.rss?q="
            + quote_plus('"Blood of Dawnwalker"')
            + "&sort=new&t=month",
            "trusted": False,
            "optional": True,
        },
    ]
    for query in SEARCH_QUERIES:
        encoded = quote_plus(query)
        sources.append({
            "name": f"Google News - {query}",
            "url": f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en",
            "trusted": False,
        })
        sources.append({
            "name": f"Bing News - {query}",
            "url": f"https://www.bing.com/news/search?q={encoded}&format=rss",
            "trusted": False,
        })
    return sources


# --- state / dedupe ---------------------------------------------------------
def get_last_run_time():
    if LAST_RUN_FILE.exists():
        try:
            return datetime.fromtimestamp(float(LAST_RUN_FILE.read_text().strip()), tz=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)


def set_last_run_time():
    LAST_RUN_FILE.write_text(str(datetime.now(timezone.utc).timestamp()))


def load_seen():
    if not SEEN_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_FILE.read_text())[-MAX_SEEN_ITEMS:])
    except Exception:
        return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(list(seen)[-MAX_SEEN_ITEMS:]))


def canonical_url(url):
    if not url:
        return ""
    parsed = urlparse(url)
    query = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
    ]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True), fragment=""))


def item_key(title, link):
    basis = canonical_url(link) or re.sub(r"\s+", " ", title.strip().lower())
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def parse_entry_time(entry):
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        value = getattr(entry, attr, None)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
    return datetime.now(timezone.utc)


def clean_text(value, limit=1200):
    if not value:
        return ""
    if isinstance(value, list):
        value = " ".join(i.get("value", "") if isinstance(i, dict) else str(i) for i in value)
    elif isinstance(value, dict):
        value = value.get("value", "")
    else:
        value = str(value)
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def relevance_score(source, title, content):
    hay = f"{title}\n{content}".lower()
    score = 0
    if source.get("trusted"):
        score += 6
    if "blood of dawnwalker" in hay:
        score += 9
    elif "dawnwalker" in hay and any(c in hay for c in DAWNWALKER_CONTEXT):
        score += 7
    score += min(5, sum(1 for s in GUIDE_SIGNALS if s in hay))
    return score


def fetch_source(source):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DawnwalkerEditorialRadar/1.0)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    }
    try:
        response = requests.get(source["url"], headers=headers, timeout=25)
        print(f"Fetching {source['name']} -> HTTP {response.status_code}")
        if response.status_code >= 400:
            return []
        parsed = feedparser.parse(response.content)
    except Exception as exc:
        label = "optional " if source.get("optional") else ""
        print(f"Error fetching {label}{source['name']}: {exc}")
        return []

    items = []
    for entry in parsed.entries:
        title = clean_text(getattr(entry, "title", ""), 240)
        link = canonical_url(getattr(entry, "link", ""))
        content = clean_text(
            getattr(entry, "summary", "") or getattr(entry, "description", "")
            or getattr(entry, "content", "")
        )
        score = relevance_score(source, title, content)
        if score < 7:
            continue
        items.append({
            "source": source["name"], "title": title, "link": link,
            "content": content, "published": parse_entry_time(entry), "score": score,
        })
    return items


def collect_new_items(last_run):
    seen = load_seen()
    new_items = []
    for source in build_sources():
        for item in fetch_source(source):
            if item["published"] <= last_run:
                continue
            key = item_key(item["title"], item["link"])
            if key in seen:
                continue
            seen.add(key)
            new_items.append(item)
    new_items.sort(key=lambda i: (i["score"], i["published"]), reverse=True)
    save_seen(seen)
    return new_items[:MAX_ITEMS_FOR_AI]


# --- Feishu -----------------------------------------------------------------
def send_to_feishu(markdown_text):
    if not FEISHU_WEBHOOK:
        print("FEISHU_WEBHOOK not set. Skipping Feishu push.")
        return
    payload = {
        "msg_type": "interactive",
        "card": {
            "elements": [{"tag": "markdown", "content": markdown_text[:18000]}],
            "header": {"title": {"content": f"{GAME_NAME} 攻略素材雷达", "tag": "plain_text"}, "template": "red"},
        },
    }
    try:
        r = requests.post(FEISHU_WEBHOOK, headers={"Content-Type": "application/json"}, json=payload, timeout=20)
        print("Feishu push response:", r.text[:200])
    except Exception as exc:
        print(f"Feishu push failed: {exc}")


# --- GitHub Contents API ----------------------------------------------------
def github_headers():
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_list_dir(path):
    """Return a list of file names in a repo directory (empty list on error/404)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{quote(path)}"
    try:
        r = requests.get(url, headers=github_headers(), params={"ref": GITHUB_BRANCH}, timeout=20)
        if r.status_code != 200:
            return []
        return [x["name"] for x in r.json() if isinstance(x, dict) and x.get("type") == "file"]
    except Exception:
        return []


def github_content_exists(path):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{quote(path)}"
    r = requests.get(url, headers=github_headers(), params={"ref": GITHUB_BRANCH}, timeout=20)
    if r.status_code == 404:
        return False
    if r.status_code >= 400:
        raise RuntimeError(f"GitHub existence check failed: {r.status_code} {r.text}")
    return True


def github_put_file(path, raw_bytes, message):
    """Commit a single file (text or binary) via the GitHub Contents API."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{quote(path)}"
    payload = {
        "message": message,
        "content": base64.b64encode(raw_bytes).decode("ascii"),
        "branch": GITHUB_BRANCH,
        "committer": {"name": GITHUB_AUTHOR_NAME, "email": GITHUB_AUTHOR_EMAIL},
        "author": {"name": GITHUB_AUTHOR_NAME, "email": GITHUB_AUTHOR_EMAIL},
    }
    r = requests.put(url, headers=github_headers(), json=payload, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"GitHub publish failed: {r.status_code} {r.text}")
    return r.json().get("content", {}).get("html_url", "")


def existing_topic_slugs():
    """All current news + guide slugs, so the model can avoid duplicating topics."""
    names = github_list_dir(GITHUB_CONTENT_DIR) + github_list_dir(GITHUB_GUIDES_DIR)
    return sorted({re.sub(r"\.(md|mdx)$", "", n) for n in names if n.endswith((".md", ".mdx"))})


# --- prompt -----------------------------------------------------------------
def build_prompt(items, existing_slugs):
    now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    existing = ", ".join(existing_slugs) or "（暂无）"
    prompt = f"""你是 {GAME_NAME}（开发商 Rebel Wolves，发行商 Bandai Namco，2026-09-03 发售）的海外攻略/资讯网站主编，站点是 dawnwalker.wiki。下面是过去约一天从官方源、社区、新闻搜索抓到的候选素材。

任务：
1. 严格过滤：只保留与《{GAME_NAME}》直接相关、且对攻略/资讯站有价值的信息。注意排除同名干扰项（"dawnwalker" 是常见词）。
2. 只要有 1 条以上有价值素材，就生成一篇可发布文章；不要只输出素材报告。
3. 先输出一份适合飞书的中文 Markdown 简报：
   - “可做选题”：3-6 个适合跟进的角度。
   - “关键信息”：每条带来源链接，区分“已确认事实”和“社区猜测/未确认”。
4. 简报之后，必须附一篇英文 SEO 文章，放在 ```markdown-publish 代码块里。代码块内只能是可直接发布的内容，frontmatter 格式严格如下（这是 Astro content collection，字段名必须完全一致）：

```markdown-publish
---
title: "自然、具体的英文标题"
description: "120-160 字符英文 meta 描述，首句点题，含自然关键词"
publishDate: "{now_utc[:10]}"
author: "Dawnwalker Guide Team"
tags: ["news", "其它相关标签"]
image: ""
imageAlt: "一句话描述题图（原创暗黑奇幻艺术，不要提到任何游戏角色名）"
sources:
  - label: "来源名称"
    url: "https://完整的来源链接"
---

正文用 Markdown：## 小标题、段落、- 列表。可以用 [内链](/guides/<已有slug>/) 指向下面列出的已有文章。
```

硬性要求：
- publishDate 必须用 UTC 日期 "{now_utc[:10]}"（YYYY-MM-DD，带引号）；不要写北京时间。
- sources 里每条都必须是真实出现在候选素材里的链接，url 必须是完整 https 链接；不要编造。
- 英文要像真人游戏编辑，自然、有观点；禁止 "In this guide", "delve into", "unlock the secrets", "game-changing", "comprehensive guide", "Let's dive in" 等 AI 套话。
- 游戏尚未发售：任何未确认内容必须标注 expected / reportedly / not yet confirmed / community-reported；不要把猜测写成官方事实，不要编造游戏机制。
- SEO 友好但不要关键词堆砌；优先攻略/资讯价值：发售与平台与版本/价格、战斗与 hex 魔法、白天人类夜晚吸血鬼的双形态、build 与技能树、Vale Sangora 世界、剧情与结局、开发者访谈、预告片机制细节。
- 标题和正文必须与下列“已存在文章”有明显差异，覆盖新角度；不要重复已有主题。
- 如果所有候选素材都只是在重复已有主题、没有新角度，就在简报里说明，并且不要输出 markdown-publish 代码块（宁可不发，也不要发重复内容）。

【已存在文章 slug（仅供正文内链引用，禁止把本文写成与它们相同的主题）】：
{existing}

当前 UTC 时间：{now_utc}

候选素材：

"""
    for idx, item in enumerate(items, 1):
        prompt += (
            f"{idx}. 来源: {item['source']}\n标题: {item['title']}\n"
            f"时间: {item['published'].isoformat()}\n链接: {item['link']}\n"
            f"相关度: {item['score']}\n内容片段: {item['content']}\n\n"
        )
    return prompt


# --- AI calls ---------------------------------------------------------------
def try_agy(prompt):
    """Run the prompt through the Antigravity subscription CLI (agy) — no API cost.
    Returns the response text, or None if agy is unavailable/failed so the caller
    can fall back to the metered AI Studio API."""
    if os.getenv("AI_EDITOR_DISABLE_AGY", "").lower() in {"1", "true", "yes"}:
        return None
    agy = os.getenv("AGY_BIN", "/root/.local/bin/agy")
    if not os.path.exists(agy):
        return None
    env = dict(os.environ, HOME=os.getenv("AGY_HOME", "/root"),
               TERM="xterm-256color", COLORTERM="truecolor")
    print("Calling agy (Antigravity subscription)...")
    try:
        res = subprocess.run(
            [agy, "--print-timeout", "9m", "-p", prompt],
            capture_output=True, text=True, timeout=600, env=env, cwd="/tmp",
        )
    except Exception as exc:
        print(f"agy invocation error: {exc}; falling back to API.")
        return None
    out = (res.stdout or "").strip()
    if res.returncode == 0 and out:
        print("Used agy (subscription) — no API cost.")
        return out
    print(f"agy unusable (rc={res.returncode}, empty={not out}); falling back to API. "
          f"stderr tail: {(res.stderr or '')[-300:]}")
    return None


def call_gemini(prompt):
    text = try_agy(prompt)
    if text:
        return text
    if not (GEMINI_API_KEY and genai):
        raise RuntimeError("GEMINI_API_KEY / google-generativeai not configured")
    print(f"Calling Gemini ({MODEL_NAME})...")
    try:
        return genai.GenerativeModel(MODEL_NAME).generate_content(prompt).text.strip()
    except Exception as exc:
        print(f"Gemini error: {exc}; trying fallback model models/gemini-pro-latest...")
        return genai.GenerativeModel("models/gemini-pro-latest").generate_content(prompt).text.strip()


def extract_publishable_article(ai_text):
    m = re.search(r"```(?:markdown-publish|publish-markdown|publish)\s*\n(.*?)\n```",
                  ai_text, re.S | re.I)
    if m and m.group(1).strip().startswith("---"):
        return m.group(1).strip()
    m = re.search(r"(?s)(---\s*\n.*?\n---\s*\n.+)$", ai_text)
    return m.group(1).strip() if m else ""


# --- frontmatter sanitizer (guarantees a build-valid Astro post) ------------
URL_RE = re.compile(r"^https?://", re.I)


def parse_article(article_md):
    """Split an article into (frontmatter_dict, body). Returns (None, '') if the
    frontmatter can't be parsed as YAML."""
    m = re.match(r"(?s)^---\s*\n(.*?)\n---\s*\n(.*)$", article_md.strip())
    if not m:
        return None, ""
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except Exception as exc:
        print(f"  frontmatter: YAML parse failed ({exc})")
        return None, ""
    if not isinstance(fm, dict):
        return None, ""
    return fm, m.group(2).lstrip("\n")


def sanitize_frontmatter(fm):
    """Coerce model output into the exact shape the Astro news schema accepts.
    Drops unknown keys, fixes types, validates source URLs. Returns a clean dict
    or None if a required field (title/description) is missing."""
    clean = {}

    title = str(fm.get("title", "")).strip()
    description = str(fm.get("description", "")).strip()
    if not title or not description:
        print("  frontmatter: missing title/description; refusing to publish.")
        return None
    clean["title"] = title
    clean["description"] = description

    # publishDate -> YYYY-MM-DD string (today UTC if absent/garbage)
    raw_date = str(fm.get("publishDate", "")).strip()
    dm = re.search(r"\d{4}-\d{2}-\d{2}", raw_date)
    clean["publishDate"] = dm.group(0) if dm else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    clean["author"] = str(fm.get("author") or "Dawnwalker Guide Team").strip()

    tags = fm.get("tags")
    if isinstance(tags, list):
        clean["tags"] = [str(t).strip() for t in tags if str(t).strip()][:8]
    else:
        clean["tags"] = ["news"]
    if not clean["tags"]:
        clean["tags"] = ["news"]

    clean["image"] = str(fm.get("image") or "").strip()
    image_alt = str(fm.get("imageAlt") or "").strip()
    if image_alt:
        clean["imageAlt"] = image_alt

    # sources -> only well-formed {label, url(https)} entries survive
    src_in = fm.get("sources")
    sources = []
    if isinstance(src_in, list):
        for s in src_in:
            if not isinstance(s, dict):
                continue
            label = str(s.get("label") or s.get("name") or "").strip()
            url = str(s.get("url") or s.get("link") or "").strip()
            if label and URL_RE.match(url):
                sources.append({"label": label, "url": url})
    if sources:
        clean["sources"] = sources[:8]

    # optional pass-through video embed (only if both present)
    video = str(fm.get("video") or "").strip()
    if video:
        clean["video"] = video
        vt = str(fm.get("videoTitle") or "").strip()
        if vt:
            clean["videoTitle"] = vt

    return clean


def render_article(fm, body):
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False).strip()
    return f"---\n{front}\n---\n\n{body.strip()}\n"


def slugify(value, max_length=70):
    value = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return (re.sub(r"-+", "-", value).strip("-") or "dawnwalker-update")[:max_length].strip("-")


# --- header image (optional) ------------------------------------------------
def _is_image_bytes(data):
    return (
        data[:4] == b"\x89PNG"
        or data[:3] == b"\xff\xd8\xff"
        or data[:4] == b"GIF8"
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    )


def optimize_image_bytes(raw_bytes):
    """Center-crop to 16:9, downscale to <=1280px wide, return (bytes, ext) as WebP.
    Falls back to the raw PNG bytes if Pillow is unavailable."""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        target_ratio = 16 / 9
        w, h = im.size
        if w / h > target_ratio + 0.01:
            new_w = int(round(h * target_ratio)); left = (w - new_w) // 2
            im = im.crop((left, 0, left + new_w, h))
        elif w / h < target_ratio - 0.01:
            new_h = int(round(w / target_ratio)); top = (h - new_h) // 2
            im = im.crop((0, top, w, top + new_h))
        w, h = im.size
        if w > 1280:
            im = im.resize((1280, round(h * 1280 / w)))
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=82, method=6)
        return buf.getvalue(), "webp"
    except Exception as exc:
        print(f"  image: Pillow unavailable ({exc}); using unoptimized source bytes")
        return raw_bytes, "png"


def _agy_generate_image_bytes(prompt):
    """Generate a header image via the Antigravity subscription CLI (agy) — no API cost."""
    if os.getenv("AI_EDITOR_DISABLE_AGY", "").lower() in {"1", "true", "yes"}:
        return None
    agy = os.getenv("AGY_BIN", "/root/.local/bin/agy")
    if not os.path.exists(agy):
        return None
    workdir = tempfile.mkdtemp(prefix="agy-img-")
    target = os.path.join(workdir, "header.png")
    env = dict(os.environ, HOME=os.getenv("AGY_HOME", "/root"),
               TERM="xterm-256color", COLORTERM="truecolor")
    instruction = (
        "Use your generate_image tool to create a single 16:9 cinematic header banner. "
        f"Theme: {prompt}. "
        f"After the image is generated, copy the resulting PNG file to exactly this path: {target} . "
        "Then print ONLY the absolute path of the PNG file on the final line. "
        "Do not ask for confirmation; just do it."
    )
    print("  image: trying agy (subscription)...")
    try:
        res = subprocess.run(
            [agy, "--dangerously-skip-permissions", "--add-dir", workdir,
             "--print-timeout", "8m", "-p", instruction],
            capture_output=True, text=True, timeout=600, env=env, cwd=workdir,
        )
    except Exception as exc:
        print(f"  image: agy invocation error: {exc}")
        return None

    candidates = []
    if os.path.exists(target):
        candidates.append(target)
    for mpath in re.findall(r"(/[^\s\"']+\.(?:png|jpe?g|webp|gif))", res.stdout or "", re.I):
        if mpath not in candidates and os.path.exists(mpath):
            candidates.append(mpath)
    for path in candidates:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except Exception:
            continue
        if len(data) > 1024 and _is_image_bytes(data):
            print("  image: agy generated a header image — no API cost")
            return data
    print(f"  image: agy produced no valid image (rc={res.returncode}); falling back to API. "
          f"stderr tail: {(res.stderr or '')[-200:]}")
    return None


def _imagen_generate_image_bytes(prompt):
    if not GEMINI_API_KEY:
        return None
    try:
        from google import genai as ggenai
        from google.genai import types as gtypes
        client = ggenai.Client(api_key=GEMINI_API_KEY)
        resp = client.models.generate_images(
            model=os.getenv("IMAGE_MODEL", "imagen-4.0-generate-001"),
            prompt=prompt,
            config=gtypes.GenerateImagesConfig(number_of_images=1, aspect_ratio="16:9"),
        )
        print("  image: generated via Imagen API")
        return resp.generated_images[0].image.image_bytes
    except Exception as exc:
        print(f"  image: Imagen API fallback failed ({exc})")
        return None


def make_header_image(base_name, title):
    """Return (repo_path, web_path, data, commit_message) or None."""
    if IMAGE_MODE == "off":
        return None
    prompt = (f"Header banner for an article about the video game {GAME_NAME} "
              f"(a dark-fantasy vampire RPG), titled '{title}'. {IMAGE_STYLE_SUFFIX}")
    raw = _agy_generate_image_bytes(prompt) or _imagen_generate_image_bytes(prompt)
    if not raw:
        print("  image: no image produced; article will publish text-only.")
        return None
    data, ext = optimize_image_bytes(raw)
    file_name = f"{base_name}.{ext}"
    repo_path = f"{GITHUB_IMAGE_DIR}/{file_name}"
    web_path = f"{IMAGE_WEB_PREFIX}/{file_name}"
    print(f"  image: prepared {repo_path} ({len(data)} bytes)")
    return repo_path, web_path, data, f"Add header image for news: {title}"


# --- publish ----------------------------------------------------------------
def publish_article(article_md):
    if not (GITHUB_TOKEN and GITHUB_REPO and GITHUB_CONTENT_DIR):
        print("GitHub publishing is not configured. Skipping commit.")
        return

    fm, body = parse_article(article_md)
    if fm is None:
        print("Could not parse article frontmatter. Skipping publish.")
        return
    fm = sanitize_frontmatter(fm)
    if fm is None:
        return

    title = fm["title"]
    date_prefix = fm["publishDate"]
    base_name = f"{date_prefix}-{slugify(title)}"
    path = f"{GITHUB_CONTENT_DIR}/{base_name}.md"
    if github_content_exists(path):
        suffix = datetime.now(timezone.utc).strftime("%H%M%S")
        base_name = f"{base_name}-{suffix}"
        path = f"{GITHUB_CONTENT_DIR}/{base_name}.md"

    if DRY_RUN:
        fm.setdefault("image", "")
        print("\n----- DRY RUN: would commit", path, "-----")
        print(render_article(fm, body)[:2500])
        return

    # Generate + commit the header image first, then point the article at it.
    # Failures here are non-fatal: the article still publishes (text-only).
    try:
        image = make_header_image(base_name, title)
        if image:
            repo_path, web_path, image_bytes, image_message = image
            github_put_file(repo_path, image_bytes, image_message)
            print(f"Published header image: {repo_path}")
            fm["image"] = web_path
    except Exception as exc:
        print(f"Header image step failed ({exc}); publishing without an image.")

    html_url = github_put_file(path, render_article(fm, body).encode("utf-8"),
                               f"Add news article: {title}")
    print(f"Published article: {path}")
    if html_url:
        print(f"GitHub URL: {html_url}")


# --- main -------------------------------------------------------------------
def main():
    last_run = get_last_run_time()
    print(f"Checking {GAME_NAME} material since {last_run.isoformat()}...")
    items = collect_new_items(last_run)

    if not items:
        print("No new relevant items. Exiting.")
        now = datetime.now(timezone.utc)
        bj = now + timedelta(hours=8)
        heartbeat = (
            f"**🟢 雷达日报：今日无新增可发布素材**\n\n"
            f"- 运行时间：{bj:%Y-%m-%d %H:%M}（北京） / {now:%H:%M} UTC\n"
            f"- 检查范围：{last_run:%Y-%m-%d %H:%M} UTC 之后发布的新内容\n"
            f"- 结果：所有数据源抓取正常，但没有发现达到相关度门槛（≥7）的新条目。\n\n"
            f"_脚本运行正常，无需处理。有新动态时会自动生成文章并推送。_"
        )
        send_to_feishu(heartbeat)
        set_last_run_time()
        return

    print(f"Found {len(items)} candidate items:")
    for it in items:
        print(f"- [{it['score']}] {it['source']}: {it['title']}")

    result = call_gemini(build_prompt(items, existing_topic_slugs()))
    article = extract_publishable_article(result)

    if DRY_RUN:
        print("\n----- DRY RUN: Gemini brief (truncated) -----\n")
        print(result[:4000])
        if article:
            publish_article(article)
        set_last_run_time()
        return

    print("Pushing editorial brief to Feishu...")
    send_to_feishu(result)
    if article:
        print("Publishable article found. Publishing to GitHub...")
        publish_article(article)
    else:
        print("No publishable article block. Brief pushed to Feishu only.")
    set_last_run_time()


if __name__ == "__main__":
    main()
