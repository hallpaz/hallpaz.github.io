#!/usr/bin/env python3
"""
Explicit Static Site Generator for Hallison Paz's Personal Website
==================================================================
Philosophy: Explicit over implicit (the "Flask philosophy").
No hidden build magic — a single, readable Python script that compiles
Markdown, YAML collections, and Jinja2 templates into a pristine dist/ directory.
"""

import argparse
import datetime
import http.server
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import frontmatter
import jinja2
import markdown
import yaml
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from pygments.formatters import HtmlFormatter

# ---------------------------------------------------------------------------
# Directory Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CONTENT_DIR = BASE_DIR / "content"
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DIST_DIR = BASE_DIR / "dist"
CONFIG_FILE = BASE_DIR / "config.yaml"


# ---------------------------------------------------------------------------
# Markdown Pipeline & Math Protection
# ---------------------------------------------------------------------------
class MathKatexPreprocessor(Preprocessor):
    """
    Protects inline $...$ and display $$...$$ LaTeX expressions by storing
    them into Markdown's htmlStash before any inline escapes or emphasis processors run.
    This guarantees that underscores (_), asterisks (*), and backslashes (\\) inside math
    are preserved 100% intact for client-side KaTeX rendering, without touching code blocks.
    """
    DISPLAY_RE = re.compile(r'(\$\$.*?\$\$)', re.DOTALL)
    INLINE_RE = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')

    def run(self, lines):
        text = "\n".join(lines)

        # 1. Protect inline code `...` temporarily so we do not match $ inside inline code
        code_stashes = []
        def stash_code(match):
            idx = len(code_stashes)
            code_stashes.append(match.group(0))
            return f"@@INLINECODE{idx}@@"

        text = re.sub(r'(`+)(.+?)\1', stash_code, text)

        # 2. Store display math in htmlStash
        def stash_display_math(match):
            math = match.group(0)
            return self.md.htmlStash.store(math)

        text = self.DISPLAY_RE.sub(stash_display_math, text)

        # 3. Store inline math in htmlStash
        def stash_inline_math(match):
            math = match.group(0)
            return self.md.htmlStash.store(math)

        text = self.INLINE_RE.sub(stash_inline_math, text)

        # 4. Restore inline code
        for idx, original_code in enumerate(code_stashes):
            text = text.replace(f"@@INLINECODE{idx}@@", original_code)

        return text.split("\n")


class KatexMathExtension(Extension):
    """Registers MathKatexPreprocessor after fenced code blocks (priority 20)."""
    def extendMarkdown(self, md):
        md.preprocessors.register(MathKatexPreprocessor(md), "katex_math", 20)


def create_markdown_renderer() -> markdown.Markdown:
    """Instantiates the Markdown parser with all required extensions."""
    return markdown.Markdown(
        extensions=[
            "fenced_code",
            "codehilite",
            "tables",
            "toc",
            "footnotes",
            KatexMathExtension(),
        ],
        extension_configs={
            "codehilite": {
                "css_class": "codehilite",
                "guess_lang": False,
                "noclasses": False,
            }
        },
    )


# ---------------------------------------------------------------------------
# Helpers: Dates, Word Count & Reading Time
# ---------------------------------------------------------------------------
def parse_date(val: Any) -> Tuple[datetime.date, str, str]:
    """
    Returns (date_obj, formatted_date_str, iso_date_str).
    Example: (date(2024, 6, 17), 'June 17, 2024', '2024-06-17')
    """
    if isinstance(val, (datetime.date, datetime.datetime)):
        d = val if isinstance(val, datetime.date) else val.date()
    elif isinstance(val, str):
        d = datetime.datetime.strptime(val.strip(), "%Y-%m-%d").date()
    else:
        raise ValueError(f"Unsupported date format: {val}")
    return d, d.strftime("%B %d, %Y"), d.isoformat()


def calculate_reading_time(text: str, wpm: int = 200) -> str:
    """Calculates approximate reading time based on word count (~200 wpm)."""
    words = len(re.findall(r"\w+", text))
    minutes = max(1, round(words / wpm))
    return f"{minutes} min read"


LANG_DISPLAY_MAP: Dict[str, str] = {
    "en": "🇬🇧 English",
    "pt": "🇧🇷 Português",
    "fr": "🇫🇷 Français",
}



# ---------------------------------------------------------------------------
# Data Loading & Validation
# ---------------------------------------------------------------------------
def load_config() -> Dict[str, Any]:
    """Loads site-wide configuration from config.yaml."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Missing configuration file: {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config or {}


def load_yaml_data(filename: str) -> Any:
    """Loads a structured collection YAML file from data/."""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def generate_pygments_css(style: str = "native") -> Path:
    """Generates universal dark Pygments syntax stylesheet ('native') used across all themes."""
    formatter = HtmlFormatter(style=style)
    css = formatter.get_style_defs('.codehilite')

    # Allow CSS variable --code-bg to control background color
    css = re.sub(r'(\.codehilite\s*\{\s*background:)[^;]+;', r'\1 var(--code-bg);', css)

    content = (
        f"/* Generated by Pygments at build time: style={style} (universal dark code theme) */\n"
        f"{css}\n"
    )

    css_path = STATIC_DIR / "css" / "pygments.css"
    css_path.parent.mkdir(parents=True, exist_ok=True)
    with open(css_path, "w", encoding="utf-8") as f:
        f.write(content)
    return css_path


# ---------------------------------------------------------------------------
# Main Site Generation Logic
# ---------------------------------------------------------------------------
def build(clean: bool = False) -> None:
    """Executes the complete end-to-end build pipeline."""
    start_time = time.time()
    print("[build] Starting site generation...")

    # 1. Clean dist/ if requested
    if clean and DIST_DIR.exists():
        print(f"[build] Cleaning existing output directory: {DIST_DIR}")
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Generate Pygments CSS stylesheet
    print("[build] Generating Pygments syntax CSS (universal dark native)...")
    generate_pygments_css("native")

    # 3. Copy static assets to dist/static/
    if STATIC_DIR.exists():
        print("[build] Copying static assets...")
        shutil.copytree(STATIC_DIR, DIST_DIR / "static", dirs_exist_ok=True)

    # 4. Load config & structured YAML collections
    print("[build] Loading config and structured data collections...")
    config = load_config()
    current_year = datetime.date.today().year

    news_raw = load_yaml_data("news.yaml")
    publications_raw = load_yaml_data("publications.yaml")
    teaching_raw = load_yaml_data("teaching.yaml")
    media_raw = load_yaml_data("media.yaml")

    # Process News
    news_categories = config.get("news_categories", [])
    news_items = []
    for item in news_raw:
        d_obj, d_str, d_iso = parse_date(item["date"])
        tag = item.get("tag", "Update")

        # Category matching: check case-insensitive substring match against each category match list in order
        matched_category = None
        color_dark = None
        color_light = None
        for cat in news_categories:
            match_patterns = cat.get("match", [])
            if any(m.lower() in tag.lower() for m in match_patterns):
                matched_category = cat.get("name")
                color_dark = cat.get("dark")
                color_light = cat.get("light")
                break

        news_items.append({
            "date_obj": d_obj,
            "date_str": d_str,
            "date_iso": d_iso,
            "tag": tag,
            "category": matched_category,
            "color_dark": color_dark,
            "color_light": color_light,
            "title": item["title"],
            "body": item["body"],
            "link": item.get("link"),
        })
    news_items.sort(key=lambda x: x["date_obj"], reverse=True)
    recent_news = news_items[:4]

    # Process Publications
    publications_list = []
    for item in publications_raw:
        d_obj, d_str, d_iso = parse_date(item["date"])
        publications_list.append({
            "title": item["title"],
            "authors": item["authors"],
            "me": item.get("me", "Hallison Paz"),
            "venue": item["venue"],
            "badge": item.get("badge"),
            "date_obj": d_obj,
            "date_str": d_str,
            "year": d_obj.year,
            "abstract": item["abstract"],
            "image": item.get("image"),
            "links": item.get("links", {}),
        })
    publications_list.sort(key=lambda x: x["date_obj"], reverse=True)

    # Group publications by year
    years_seen = []
    pub_groups = {}
    for pub in publications_list:
        y = pub["year"]
        if y not in pub_groups:
            years_seen.append(y)
            pub_groups[y] = []
        pub_groups[y].append(pub)
    publications_by_year = [{"year": y, "publications": pub_groups[y]} for y in years_seen]

    # Process Teaching
    teaching_by_year = []
    for group in teaching_raw:
        teaching_by_year.append({
            "year": group["year"],
            "courses": group["courses"],
        })
    teaching_by_year.sort(key=lambda x: x["year"], reverse=True)

    # Process Media & Talks
    media_items = []
    for item in media_raw:
        d_obj, d_str, d_iso = parse_date(item["date"])
        media_items.append({
            "type": item["type"],
            "title": item["title"],
            "source": item["source"],
            "date_obj": d_obj,
            "date_str": d_str,
            "date_iso": d_iso,
            "duration": item.get("duration"),
            "description": item["description"],
            "url": item["url"],
            "thumbnail": item["thumbnail"],
        })
    media_items.sort(key=lambda x: x["date_obj"], reverse=True)

    # 5. Parse Markdown Content
    print("[build] Parsing Markdown content and blog posts...")
    md = create_markdown_renderer()

    # Parse about.md
    about_file = CONTENT_DIR / "about.md"
    if not about_file.exists():
        raise FileNotFoundError(f"Missing about file: {about_file}")
    with open(about_file, "r", encoding="utf-8") as f:
        about_post = frontmatter.load(f)
    about_html = md.convert(about_post.content)
    about_data = {
        "meta": about_post.metadata,
        "html": about_html,
    }

    # Parse Blog Posts
    blog_dir = CONTENT_DIR / "blog"
    blog_posts = []
    if blog_dir.exists():
        for md_path in blog_dir.glob("*.md"):
            with open(md_path, "r", encoding="utf-8") as f:
                post = frontmatter.load(f)

            if post.metadata.get("draft", False):
                print(f"[build] Skipping draft blog post: {md_path.name}")
                continue

            slug = md_path.stem
            d_obj, d_str, d_iso = parse_date(post.metadata["date"])
            read_time = calculate_reading_time(post.content)
            site_owner = config.get("site_name", "Hallison Paz")
            author = post.metadata.get("author") or site_owner
            default_lang = config.get("default_lang", "en")
            lang = post.metadata.get("lang") or default_lang
            lang_display = LANG_DISPLAY_MAP.get(lang, lang.upper())

            # Convert markdown body (preserving math via KatexMathExtension)
            # Reset markdown instance to clear previous footnotes/state
            md.reset()
            body_html = md.convert(post.content)

            blog_posts.append({
                "slug": slug,
                "title": post.metadata["title"],
                "author": author,
                "lang": lang,
                "lang_display": lang_display,
                "date_obj": d_obj,
                "date_str": d_str,
                "date_iso": d_iso,
                "tags": post.metadata.get("tags", []),
                "summary": post.metadata.get("summary", ""),
                "read_time": read_time,
                "html": body_html,
                "url": f"/blog/{slug}/",
            })
    blog_posts.sort(key=lambda x: x["date_obj"], reverse=True)

    # 6. Initialize Jinja2 Environment with StrictUndefined
    # Fails loudly if a template references a missing field
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=jinja2.StrictUndefined,
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )

    def render_and_write(template_name: str, output_rel_path: str, context: Dict[str, Any]) -> None:
        """Renders a Jinja2 template and writes the output file in dist/."""
        template = jinja_env.get_template(template_name)
        rendered = template.render(
            config=config,
            current_year=current_year,
            **context,
        )
        out_file = DIST_DIR / output_rel_path
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(rendered)

    # 7. Render Clean URLs Pages
    print("[build] Rendering pages with Jinja2...")

    # Home Page: dist/index.html
    render_and_write(
        "index.html",
        "index.html",
        {
            "current_page": "about",
            "about": about_data,
            "recent_news": recent_news,
        },
    )

    # News Page: dist/news/index.html
    render_and_write(
        "news.html",
        "news/index.html",
        {
            "current_page": "news",
            "news_items": news_items,
        },
    )

    # Publications Page: dist/publications/index.html
    render_and_write(
        "publications.html",
        "publications/index.html",
        {
            "current_page": "publications",
            "publications_by_year": publications_by_year,
        },
    )

    # Teaching Page: dist/teaching/index.html
    render_and_write(
        "teaching.html",
        "teaching/index.html",
        {
            "current_page": "teaching",
            "teaching_by_year": teaching_by_year,
        },
    )

    # Media & Talks Page: dist/media/index.html
    render_and_write(
        "media.html",
        "media/index.html",
        {
            "current_page": "media",
            "media_items": media_items,
        },
    )

    # Blog Listing: dist/blog/index.html
    render_and_write(
        "blog_list.html",
        "blog/index.html",
        {
            "current_page": "blog",
            "blog_posts": blog_posts,
        },
    )

    # Individual Blog Posts: dist/blog/<slug>/index.html
    for post in blog_posts:
        render_and_write(
            "blog_post.html",
            f"blog/{post['slug']}/index.html",
            {
                "current_page": "blog",
                "post": post,
            },
        )

    # 8. Generate sitemap.xml and feed.xml
    print("[build] Generating sitemap.xml and feed.xml...")
    generate_sitemap(config, blog_posts)
    generate_rss_feed(config, blog_posts)

    elapsed = time.time() - start_time
    print(f"[build] Build completed successfully in {elapsed:.2f}s -> {DIST_DIR}")


# ---------------------------------------------------------------------------
# Sitemap & RSS Feeds
# ---------------------------------------------------------------------------
def generate_sitemap(config: Dict[str, Any], blog_posts: List[Dict[str, Any]]) -> None:
    """Generates standard sitemap.xml in dist/."""
    base_url = config.get("base_url", "https://hallpaz.github.io").rstrip("/")
    today = datetime.date.today().isoformat()

    static_routes = ["/", "/news/", "/publications/", "/teaching/", "/media/", "/blog/"]
    urls = []
    for route in static_routes:
        urls.append(f"  <url>\n    <loc>{base_url}{route}</loc>\n    <lastmod>{today}</lastmod>\n  </url>")

    for post in blog_posts:
        urls.append(f"  <url>\n    <loc>{base_url}{post['url']}</loc>\n    <lastmod>{post['date_iso']}</lastmod>\n  </url>")

    sitemap_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    with open(DIST_DIR / "sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap_content)


def generate_rss_feed(config: Dict[str, Any], blog_posts: List[Dict[str, Any]]) -> None:
    """Generates standard RSS 2.0 feed in dist/feed.xml."""
    base_url = config.get("base_url", "https://hallpaz.github.io").rstrip("/")
    site_name = config.get("site_name", "Hallison Paz")
    description = config.get("description", "Research notes and articles.")

    items = []
    for post in blog_posts:
        pub_date = post["date_obj"].strftime("%a, %d %b %Y 00:00:00 GMT")
        post_link = f"{base_url}{post['url']}"
        items.append(
            "    <item>\n"
            f"      <title>{post['title']}</title>\n"
            f"      <link>{post_link}</link>\n"
            f"      <guid isPermaLink=\"true\">{post_link}</guid>\n"
            f"      <pubDate>{pub_date}</pubDate>\n"
            f"      <description><![CDATA[{post['summary']}]]></description>\n"
            "    </item>"
        )

    feed_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{site_name} - Blog</title>\n"
        f"    <link>{base_url}/blog/</link>\n"
        f"    <description>{description}</description>\n"
        "    <language>en-us</language>\n"
        f'    <atom:link href="{base_url}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items)
        + "\n  </channel>\n"
        "</rss>\n"
    )
    with open(DIST_DIR / "feed.xml", "w", encoding="utf-8") as f:
        f.write(feed_content)


# ---------------------------------------------------------------------------
# Development Server & Watchdog Auto-Rebuilder
# ---------------------------------------------------------------------------
def serve_and_watch(port: int = 8000) -> None:
    """Runs a local http.server and watches source directories for automatic rebuild."""
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        print("[error] 'watchdog' package is required for --serve. Install with: pip install watchdog")
        sys.exit(1)

    # Initial build
    build(clean=False)

    class ChangeHandler(FileSystemEventHandler):
        def __init__(self):
            self.last_rebuild = 0.0
            self.lock = threading.Lock()

        def on_any_event(self, event):
            # Ignore directory events and changes within dist/
            if event.is_directory or "dist" in event.src_path:
                return

            now = time.time()
            with self.lock:
                # Debounce rebuilds by 0.4s
                if now - self.last_rebuild > 0.4:
                    self.last_rebuild = now
                    print(f"\n[watchdog] File changed: {event.src_path}")
                    try:
                        build(clean=False)
                    except Exception as e:
                        print(f"[watchdog] Rebuild error: {e}", file=sys.stderr)

    observer = Observer()
    handler = ChangeHandler()

    for watch_dir in [CONTENT_DIR, DATA_DIR, TEMPLATES_DIR, STATIC_DIR]:
        if watch_dir.exists():
            observer.schedule(handler, str(watch_dir), recursive=True)
            print(f"[watcher] Watching {watch_dir.name}/")

    # Also watch config.yaml
    observer.schedule(handler, str(BASE_DIR), recursive=False)
    observer.start()

    # Simple HTTP Server rooted at dist/
    class DistHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    server = http.server.ThreadingHTTPServer(("", port), DistHTTPRequestHandler)
    print(f"\n========================================================")
    print(f"  Serving static site at: http://localhost:{port}/")
    print(f"  Watching for edits in content/, data/, templates/, static/")
    print(f"  Press Ctrl+C to terminate server.")
    print(f"========================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Shutting down...")
    finally:
        observer.stop()
        observer.join()
        server.server_close()
        print("[server] Stopped.")


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Explicit Static Site Generator for Hallison Paz's personal website."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe the dist/ output directory before building.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start local HTTP server and watch directories for auto-rebuilding.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to use for local development server (default: 8000).",
    )

    args = parser.parse_args()

    if args.serve:
        serve_and_watch(port=args.port)
    else:
        build(clean=args.clean)


if __name__ == "__main__":
    main()
