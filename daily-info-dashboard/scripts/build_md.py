from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from deep_translator import GoogleTranslator


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"
OUTPUT_PATH = BASE_DIR / "output" / "daily.md"
SITE_DIR = BASE_DIR / "output" / "site"
TOP_GLOBAL = 5
TOP_PER_TOPIC = 3

USEFULNESS_KEYWORDS = {
    "workflow": 5,
    "automation": 5,
    "productivity": 5,
    "analysis": 4,
    "analytics": 4,
    "dashboard": 4,
    "guide": 4,
    "how to": 4,
    "tutorial": 4,
    "feature": 3,
    "launch": 3,
    "integration": 3,
    "use case": 3,
    "best practice": 3,
    "agent": 3,
    "reporting": 3,
    "tracking": 3,
    "measurement": 3,
}

BUSINESS_SKILLS_KEYWORDS = {
    "task management": 6,
    "project management": 6,
    "prioritization": 5,
    "decision making": 5,
    "meeting notes": 5,
    "meeting agenda": 5,
    "facilitation": 5,
    "collaboration": 5,
    "communication": 5,
    "stakeholder": 4,
    "documentation": 5,
    "knowledge sharing": 5,
    "presentation": 5,
    "slide": 4,
    "writing": 4,
    "remote work": 4,
    "teamwork": 4,
    "1:1": 4,
    "1on1": 4,
}


def find_latest_json(raw_dir: Path) -> Path:
    candidates = sorted(raw_dir.glob("*.json"))
    if not candidates:
        raise FileNotFoundError("No raw JSON files found. Run scripts/fetch.py first.")
    return candidates[-1]


def load_payload(json_path: Path) -> dict[str, Any]:
    with json_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def tokenize(text: str) -> str:
    normalized = (text or "").casefold()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def score_item(item: dict[str, Any], target_date: str) -> tuple[int, list[str]]:
    title = tokenize(item.get("title", ""))
    summary = tokenize(item.get("summary", ""))
    combined = f"{title} {summary}"

    score = 0
    reasons: list[str] = []

    topic_count = len(item.get("matched_topics", []))
    if topic_count:
        topic_score = topic_count * 6
        score += topic_score
        reasons.append(f"関連トピックが {topic_count} 件")

    for keyword, weight in USEFULNESS_KEYWORDS.items():
        if keyword in combined:
            score += weight
            reasons.append(f"`{keyword}` に関する実務ヒント")

    if "Business Skills" in item.get("matched_topics", []):
        score += 4
        reasons.append("ビジネス基礎スキルに関連")

        for keyword, weight in BUSINESS_SKILLS_KEYWORDS.items():
            if keyword in combined:
                score += weight
                reasons.append(f"`{keyword}` に関する協働・業務改善ヒント")

    if item.get("source_category") in {"Data Analytics", "Marketing Analytics"}:
        score += 3
        reasons.append("分析業務に近い情報源")
    elif item.get("source_category") == "Business Skills":
        score += 3
        reasons.append("ビジネススキル系の情報源")

    published_at = item.get("published_at", "")
    if published_at:
        if published_at == target_date:
            score += 6
            reasons.append("対象日の記事")
        else:
            try:
                days_old = (date.fromisoformat(target_date) - date.fromisoformat(published_at)).days
                if days_old <= 7:
                    score += 2
                    reasons.append("直近 7 日の記事")
            except ValueError:
                pass

    if len(reasons) == 0:
        reasons.append("キーワード一致")

    return score, reasons[:3]


def build_summary(item: dict[str, Any]) -> str:
    summary = (item.get("summary") or "").strip()
    if not summary:
        return "RSS の本文抜粋がありませんでした。"
    if len(summary) <= 150:
        return summary
    return summary[:147].rstrip() + "..."


def build_read_recommendation(score: int) -> str:
    if score >= 24:
        return "かなり読む価値あり"
    if score >= 16:
        return "読む価値あり"
    if score >= 10:
        return "気になれば読む"
    return "優先度は低め"


def select_top_items(items: list[dict[str, Any]], target_date: str) -> list[dict[str, Any]]:
    scored_items: list[dict[str, Any]] = []

    for item in items:
        score, reasons = score_item(item, target_date)
        item_copy = dict(item)
        item_copy["importance_score"] = score
        item_copy["importance_reasons"] = reasons
        scored_items.append(item_copy)

    scored_items.sort(
        key=lambda item: (
            item.get("importance_score", 0),
            item.get("published_at", ""),
            item.get("title", ""),
        ),
        reverse=True,
    )
    return scored_items


def translate_text(text: str, translator: GoogleTranslator | None, cache: dict[str, str]) -> str:
    if not text:
        return ""
    if text in cache:
        return cache[text]

    translated = text
    if translator is not None:
        try:
            translated = translator.translate(text)
        except Exception:
            translated = text

    cache[text] = translated
    return translated


def group_by_primary_topic(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for item in items:
        topic = (item.get("matched_topics") or ["Other"])[0]
        grouped.setdefault(topic, []).append(item)

    return dict(sorted(grouped.items()))


def format_item_lines(
    item: dict[str, Any],
    translator: GoogleTranslator | None,
    text_cache: dict[str, str],
) -> list[str]:
    published_at = item.get("published_at") or "不明"
    original_title = item.get("title", "No Title")
    translated_title = translate_text(original_title, translator, text_cache)
    score = item.get("importance_score", 0)
    translated_summary = translate_text(build_summary(item), translator, text_cache)
    recommendation = build_read_recommendation(score)

    return [
        f"### {translated_title}",
        f"- 情報源: {item.get('source_name', '')} | 公開日: {published_at}",
        f"- 重要度: {score} | 読むべき度: {recommendation}",
        f"- 内容要約: {translated_summary}",
        f"- URL: {item.get('url', '')}",
        "",
    ]


def render_item_html(
    item: dict[str, Any],
    translator: GoogleTranslator | None,
    text_cache: dict[str, str],
    target_date: str,
) -> str:
    published_at = item.get("published_at") or "不明"
    original_title = item.get("title", "No Title")
    translated_title = translate_text(original_title, translator, text_cache)
    translated_summary = translate_text(build_summary(item), translator, text_cache)
    score = item.get("importance_score", 0)
    recommendation = build_read_recommendation(score)
    url = item.get("url", "")
    source_name = item.get("source_name", "")
    item_id = html.escape(url)
    topic_tags = ", ".join(item.get("matched_topics", []))

    return f"""
    <article class="card" data-bookmark-id="{item_id}" data-title="{html.escape(translated_title)}" data-url="{item_id}" data-date="{html.escape(target_date)}">
      <div class="topline">
        <span class="score">重要度 {score}</span>
        <span class="recommend">{html.escape(recommendation)}</span>
        <button class="bookmark-btn" type="button" data-bookmark-toggle>☆ 保存</button>
      </div>
      <h3>{html.escape(translated_title)}</h3>
      <p class="meta">{html.escape(source_name)} | {html.escape(published_at)} | {html.escape(topic_tags)}</p>
      <p class="summary">{html.escape(translated_summary)}</p>
      <p class="linkline"><a href="{html.escape(url)}" target="_blank" rel="noreferrer">記事を開く</a></p>
    </article>
    """.strip()


def build_bookmark_script() -> str:
    return """
<script>
const BOOKMARK_KEY = "daily-info-dashboard-bookmarks";

function loadBookmarks() {
  try {
    return JSON.parse(localStorage.getItem(BOOKMARK_KEY) || "[]");
  } catch (error) {
    return [];
  }
}

function saveBookmarks(bookmarks) {
  localStorage.setItem(BOOKMARK_KEY, JSON.stringify(bookmarks));
}

function isBookmarked(url, bookmarks) {
  return bookmarks.some((item) => item.url === url);
}

function renderBookmarkList(bookmarks) {
  const container = document.querySelector("[data-bookmark-list]");
  if (!container) return;

  if (bookmarks.length === 0) {
    container.innerHTML = "<p class=\\"bookmark-empty\\">保存した記事はまだありません。</p>";
    return;
  }

  const sorted = [...bookmarks].sort((a, b) => (a.savedAt < b.savedAt ? 1 : -1));
  container.innerHTML = sorted.map((item) => `
    <a class="bookmark-item" href="${item.pageUrl}#bookmark-${encodeURIComponent(item.url)}">
      <strong>${item.title}</strong>
      <span>${item.date}</span>
    </a>
  `).join("");
}

function syncButtons(bookmarks) {
  document.querySelectorAll("[data-bookmark-toggle]").forEach((button) => {
    const card = button.closest("[data-bookmark-id]");
    if (!card) return;
    const url = card.dataset.bookmarkId;
    const active = isBookmarked(url, bookmarks);
    button.textContent = active ? "★ 保存済み" : "☆ 保存";
    button.classList.toggle("active", active);
    card.id = `bookmark-${encodeURIComponent(url)}`;
  });
}

function toggleBookmark(button) {
  const card = button.closest("[data-bookmark-id]");
  if (!card) return;

  const url = card.dataset.bookmarkId;
  const title = card.dataset.title;
  const date = card.dataset.date;
  let bookmarks = loadBookmarks();

  if (isBookmarked(url, bookmarks)) {
    bookmarks = bookmarks.filter((item) => item.url !== url);
  } else {
    bookmarks.push({
      url,
      title,
      date,
      pageUrl: window.location.pathname,
      savedAt: new Date().toISOString()
    });
  }

  saveBookmarks(bookmarks);
  syncButtons(bookmarks);
  renderBookmarkList(bookmarks);
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-bookmark-toggle]");
  if (!button) return;
  toggleBookmark(button);
});

document.addEventListener("DOMContentLoaded", () => {
  const bookmarks = loadBookmarks();
  syncButtons(bookmarks);
  renderBookmarkList(bookmarks);
});
</script>
"""


def build_html(
    generated_at: str,
    target_date: str,
    ranked_items: list[dict[str, Any]],
    translator: GoogleTranslator | None,
    text_cache: dict[str, str],
) -> str:
    top_global_items = ranked_items[:TOP_GLOBAL]
    grouped = group_by_primary_topic(ranked_items)

    sections: list[str] = []
    top_cards = "\n".join(
        render_item_html(item, translator, text_cache, target_date)
        for item in top_global_items
    )
    sections.append(f"<section><h2>全体トップ5</h2><div class=\"cards\">{top_cards}</div></section>")

    for topic, topic_items in grouped.items():
        cards = "\n".join(
            render_item_html(item, translator, text_cache, target_date)
            for item in topic_items[:TOP_PER_TOPIC]
        )
        sections.append(
            f"<section><h2>{html.escape(topic)}</h2><div class=\"cards\">{cards}</div></section>"
        )

    body_sections = "\n".join(sections)
    title = f"Daily Info Dashboard {target_date}"

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4efe6;
      --panel: #fffaf2;
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #a64b2a;
      --accent-soft: #f4d7c8;
      --line: #eadfce;
      --shadow: 0 10px 24px rgba(73, 41, 19, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, #f8e5ce 0, transparent 32%),
        linear-gradient(180deg, #f7f2ea 0%, var(--bg) 100%);
      color: var(--text);
    }}
    .wrap {{
      max-width: 760px;
      margin: 0 auto;
      padding: 18px 14px 32px;
    }}
    header, .bookmark-panel {{
      background: rgba(255, 250, 242, 0.88);
      border: 1px solid rgba(234, 223, 206, 0.8);
      border-radius: 20px;
      padding: 16px;
      box-shadow: var(--shadow);
    }}
    header {{
      margin-bottom: 14px;
    }}
    .bookmark-panel {{
      margin-bottom: 10px;
    }}
    h1, h2, h3 {{
      line-height: 1.3;
      margin: 0;
    }}
    h1 {{
      font-size: 1.55rem;
      margin-bottom: 6px;
    }}
    h2 {{
      font-size: 1.08rem;
      margin: 18px 0 10px;
    }}
    h3 {{
      font-size: 1rem;
      margin-bottom: 6px;
    }}
    p {{
      margin: 0 0 8px;
      line-height: 1.55;
    }}
    .lead, .meta {{
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .cards {{
      display: grid;
      gap: 10px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px;
      box-shadow: var(--shadow);
    }}
    .topline {{
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 6px;
    }}
    .score {{
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 700;
      font-size: 0.78rem;
    }}
    .recommend {{
      color: var(--accent);
      font-size: 0.8rem;
      font-weight: 700;
    }}
    .bookmark-btn {{
      margin-left: auto;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 999px;
      padding: 5px 9px;
      font-size: 0.78rem;
      cursor: pointer;
    }}
    .bookmark-btn.active {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}
    .summary {{
      font-size: 0.92rem;
      margin-bottom: 6px;
    }}
    .linkline {{
      margin-bottom: 0;
      font-size: 0.9rem;
    }}
    a {{
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
    }}
    .bookmark-list {{
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }}
    .bookmark-item {{
      display: block;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      box-shadow: var(--shadow);
    }}
    .bookmark-item span {{
      display: block;
      color: var(--muted);
      font-size: 0.84rem;
      margin-top: 2px;
    }}
    .bookmark-empty {{
      color: var(--muted);
      margin-top: 8px;
    }}
    .footer-links {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      margin-top: 22px;
      color: var(--muted);
      font-size: 0.9rem;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <header>
      <h1>Daily Info Dashboard</h1>
      <p class="lead">対象日: {html.escape(target_date)}</p>
      <p class="lead">更新日: {html.escape(generated_at)}</p>
      <p class="lead">昨日更新された記事から、業務活用や生活改善につながりやすいものを重要度順に並べています。</p>
    </header>
    <section class="bookmark-panel">
      <h2>ブックマーク</h2>
      <p class="lead">気になった記事を保存して、あとでスマホから見返せます。</p>
      <div class="bookmark-list" data-bookmark-list></div>
    </section>
    {body_sections}
    <div class="footer-links">
      <a href="../archive/index.html">日付一覧へ</a>
      <a href="../index.html">最新ページへ</a>
    </div>
  </main>
  {build_bookmark_script()}
</body>
</html>
"""


def build_archive_index(dates: list[str]) -> str:
    links = "\n".join(
        f'<li><a href="../{html.escape(day)}/index.html">{html.escape(day)} の記事ページ</a></li>'
        for day in sorted(dates, reverse=True)
    )

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Info Dashboard Archive</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7f2ea;
      color: #1f2937;
    }}
    main {{
      max-width: 720px;
      margin: 0 auto;
      padding: 24px 16px 40px;
    }}
    .panel {{
      background: #fffaf2;
      border: 1px solid #eadfce;
      border-radius: 20px;
      padding: 20px;
    }}
    h1 {{
      margin-top: 0;
    }}
    ul {{
      padding-left: 20px;
      line-height: 1.9;
    }}
    a {{
      color: #a64b2a;
      text-decoration: none;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <main>
    <div class="panel">
      <h1>Daily Info Dashboard</h1>
      <p>日付ごとの記事ページ一覧です。</p>
      <p><a href="../index.html">最新ページを見る</a></p>
      <ul>
        {links}
      </ul>
    </div>
  </main>
</body>
</html>
"""


def build_latest_index(latest_date: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url=./{html.escape(latest_date)}/index.html">
  <title>Daily Info Dashboard</title>
</head>
<body>
  <p><a href="./{html.escape(latest_date)}/index.html">最新ページへ移動</a></p>
</body>
</html>
"""


def write_site_pages(
    generated_at: str,
    target_date: str,
    ranked_items: list[dict[str, Any]],
    translator: GoogleTranslator | None,
    text_cache: dict[str, str],
) -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    day_dir = SITE_DIR / target_date
    day_dir.mkdir(parents=True, exist_ok=True)
    html_text = build_html(generated_at, target_date, ranked_items, translator, text_cache)
    (day_dir / "index.html").write_text(html_text, encoding="utf-8")

    archive_dir = SITE_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    existing_dates = [
        path.name
        for path in SITE_DIR.iterdir()
        if path.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.name)
    ]
    (archive_dir / "index.html").write_text(build_archive_index(existing_dates), encoding="utf-8")
    (SITE_DIR / "index.html").write_text(build_latest_index(target_date), encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")


def build_markdown(generated_at: str, target_date: str, items: list[dict[str, Any]]) -> str:
    ranked_items = select_top_items(items, target_date)
    top_global_items = ranked_items[:TOP_GLOBAL]
    grouped = group_by_primary_topic(ranked_items)
    text_cache: dict[str, str] = {}

    try:
        translator: GoogleTranslator | None = GoogleTranslator(source="auto", target="ja")
    except Exception:
        translator = None

    lines: list[str] = [
        "# Daily Info Dashboard",
        f"対象日: {target_date}",
        f"更新日: {generated_at}",
        "",
        "昨日更新された記事から、業務活用や生活改善につながりやすいものを重要度順に並べています。",
        "",
    ]

    if not ranked_items:
        lines.extend(
            [
                "関連する記事が見つかりませんでした。",
                "",
            ]
        )
        write_site_pages(generated_at, target_date, ranked_items, translator, text_cache)
        return "\n".join(lines)

    lines.append("## 全体トップ5")
    lines.append("")

    for item in top_global_items:
        lines.extend(format_item_lines(item, translator, text_cache))

    for topic, topic_items in grouped.items():
        lines.append(f"## {topic}")
        lines.append("")

        for item in topic_items[:TOP_PER_TOPIC]:
            lines.extend(format_item_lines(item, translator, text_cache))

    write_site_pages(generated_at, target_date, ranked_items, translator, text_cache)
    return "\n".join(lines)


def main() -> None:
    latest_json = find_latest_json(RAW_DIR)
    payload = load_payload(latest_json)
    generated_at = payload.get("generated_at", "")
    target_date = payload.get("target_date") or payload.get("generated_at", "")
    items = payload.get("items", [])
    markdown = build_markdown(generated_at, target_date, items)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(markdown, encoding="utf-8")

    print(f"Generated {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

