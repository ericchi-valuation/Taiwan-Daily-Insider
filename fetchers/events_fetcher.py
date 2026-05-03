"""
Taipei Events Fetcher
=======================
Fetches today's cultural, sports, and city events in Taipei from Google News
and other free/public RSS sources. Returns a short list of highlights for the podcast script.
"""

import feedparser
from datetime import datetime, timezone, timedelta
import pytz
import time

TAIPEI_TZ = pytz.timezone("Asia/Taipei")

def _is_today_or_upcoming(entry, days_ahead=2):
    """
    Check if a feed entry is for today or within the next `days_ahead` days.
    Falls back to True if the entry has no parseable date.
    """
    now_taipei = datetime.now(TAIPEI_TZ)
    cutoff_past  = now_taipei - timedelta(hours=12)  # allow events that started tonight
    cutoff_future = now_taipei + timedelta(days=days_ahead)

    for attr in ('published_parsed', 'updated_parsed'):
        t = getattr(entry, attr, None)
        if t is None:
            continue
        try:
            dt_utc = datetime(*t[:6], tzinfo=timezone.utc)
            dt_tpe = dt_utc.astimezone(TAIPEI_TZ)
            return cutoff_past <= dt_tpe <= cutoff_future
        except Exception:
            continue

    return True


def _parse_feed(url, limit=4, label=""):
    """Fetch an RSS feed and return a list of event dicts."""
    events = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if len(events) >= limit:
                break
            if not _is_today_or_upcoming(entry):
                continue
            title   = entry.get("title", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            link    = entry.get("link", "")
            if not title:
                continue
            events.append({
                "title":   title,
                "summary": summary[:200] if summary else "",
                "link":    link,
                "source":  label,
            })
    except Exception as e:
        print(f"  ⚠️  Could not parse events feed ({label}): {e}")
    return events


def get_taipei_events(limit=3):
    """
    Aggregate today's Taipei events from free RSS/web sources.
    Returns up to `limit` events suitable for inclusion in the podcast script.
    """
    print("🎭 Fetching Taipei daily events...")
    all_events = []

    # ── Source 1: Google News (Taipei Events - Chinese) ─────────────────────
    google_url = (
        "https://news.google.com/rss/search"
        "?q=(台北+OR+新北)+AND+(活動+OR+展覽+OR+演唱會+OR+市集)+when:2d"
        "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    all_events.extend(_parse_feed(google_url, limit=4, label="Taipei Local Events"))
    time.sleep(0.5)

    # ── Source 2: Google News (Taiwan Arts & Culture - Chinese) ──────────────
    culture_url = (
        "https://news.google.com/rss/search"
        "?q=(台灣+OR+台北)+AND+(藝文+OR+音樂祭+OR+快閃店)+when:2d"
        "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    all_events.extend(_parse_feed(culture_url, limit=3, label="Arts & Culture"))
    time.sleep(0.5)

    # ── Deduplicate by title (case-insensitive) ───────────────────────────────
    seen   = set()
    unique = []
    for ev in all_events:
        key = ev["title"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    # ── Return top N events ───────────────────────────────────────────────────
    selected = unique[:limit]
    if selected:
        print(f"  ✔️  Found {len(selected)} Taipei/Taiwan events:")
        for ev in selected:
            print(f"     • [{ev['source']}] {ev['title']}")
    else:
        print("  ⚠️  No Taipei events found today.")

    return selected


if __name__ == "__main__":
    events = get_taipei_events(limit=3)
    print("\n--- Taipei Events ---")
    for ev in events:
        print(f"[{ev['source']}] {ev['title']}")
        print(f"  {ev['summary'][:120]}")
        print(f"  {ev['link']}\n")
