import feedparser
import time
from datetime import datetime, timezone, timedelta

# 排除八卦花邊新聞的基礎黑名單 (後續 LLM 會再做第二層把關)
GOSSIP_KEYWORDS = [
    '偷吃', '摩鐵', '小王', '小三', '出軌', '不倫', '抓姦', '綠帽',
    '激戰', '走光', '露點', '豔片', '私密片', '小胖'
]


def is_trash_news(title, summary):
    text = title + summary
    return any(kw in text for kw in GOSSIP_KEYWORDS)


def _is_recent(entry, max_hours=36):
    """
    Return True if the feed entry was published within the last `max_hours`.
    Uses published_parsed or updated_parsed from feedparser (UTC struct_time).
    Falls back to True if no date is present (to avoid over-filtering).

    36-hour window: captures today's news + yesterday evening (for early-morning runs).
    Prevents stale articles from generating outdated commentary like
    "tomorrow's vote" when the event has already passed.
    """
    for attr in ('published_parsed', 'updated_parsed'):
        t = getattr(entry, attr, None)
        if t is None:
            continue
        try:
            pub_utc = datetime(*t[:6], tzinfo=timezone.utc)
            cutoff  = datetime.now(timezone.utc) - timedelta(hours=max_hours)
            return pub_utc >= cutoff
        except Exception:
            continue

    return True  # no date info → include (don't silently drop undated feeds)


def fetch_rss_news(feed_url, limit=3, max_retries=3, max_hours=36):
    """抓取單一 RSS 來源的新聞，包含重試機制與時效過濾"""
    entries = []

    for attempt in range(max_retries):
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return entries

            for entry in feed.entries:
                if len(entries) >= limit:
                    break

                # ── 時效過濾：跳過超過 max_hours 的舊文章 ──────────
                if not _is_recent(entry, max_hours=max_hours):
                    continue

                title   = entry.get('title', 'No Title').strip()
                summary = entry.get('summary', entry.get('description', ''))

                if not title:
                    continue

                # 爬蟲層的基礎過濾：看到花邊新聞關鍵字直接跳過
                if is_trash_news(title, summary):
                    continue

                entries.append({
                    'title':   title,
                    'summary': summary,
                    'link':    entry.get('link', '')
                })

            return entries

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"Error parsing feed {feed_url}: {e}")
                return entries

    return entries


def get_daily_news(items_per_source=2):
    """
    獲取台灣主要新聞、商業、與財經來源。
    主要客群：外籍就業金卡持卡人、外商高階主管、在台外籍專業人士。

    所有文章限制在 36 小時內，防止過期新聞汙染播報稿。
    """
    sources = {
        # --- 一般要聞 ---
        '中央社 CNA (英文國際版)': 'https://feedx.net/rss/focustaiwan.xml',
        'Taipei Times (英文時事)': 'https://www.taipeitimes.com/xml/index.rss',
        'Focus Taiwan (英文即時)': (
            'https://news.google.com/rss/search?q=site:focustaiwan.tw+when:2d'
            '&hl=en-TW&gl=TW&ceid=TW:en'
        ),

        # --- 商業與財經 ---
        '經濟日報 (財經深度)': (
            'https://news.google.com/rss/search?q=site:money.udn.com+when:1d'
            '&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
        ),
        '工商時報 (產業財經)': (
            'https://news.google.com/rss/search?q=site:ctee.com.tw+when:1d'
            '&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
        ),
        '台股與外資動向': (
            'https://news.google.com/rss/search?q=(外資+OR+台股+OR+TAIEX)+when:1d'
            '&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
        ),
        'NTD 匯率與央行政策': (
            'https://news.google.com/rss/search?q=(新台幣+OR+NTD+OR+央行+OR+匯率)+when:1d'
            '&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
        ),

        # --- 科技與半導體 ---
        'TSMC 與半導體': (
            'https://news.google.com/rss/search?q=(TSMC+OR+台積電+OR+半導體)+when:1d'
            '&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
        ),
        '科技新聞 (英文)': (
            'https://news.google.com/rss/search?q=Taiwan+tech+semiconductor+when:1d'
            '&hl=en-TW&gl=TW&ceid=TW:en'
        ),

        # --- 政策與外籍人士相關 ---
        '外籍人才與政策': (
            'https://news.google.com/rss/search?q=(Gold+Card+OR+外籍人才+OR+勞動部+OR+移民署)+when:2d'
            '&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'
        ),
        '兩岸與地緣政治': (
            'https://news.google.com/rss/search?q=(Taiwan+China+OR+兩岸+OR+國防)+when:1d'
            '&hl=en&gl=US&ceid=US:en'
        ),
    }

    all_news = {}
    for source_name, url in sources.items():
        try:
            articles = fetch_rss_news(url, limit=items_per_source)
            if articles:
                all_news[source_name] = articles
        except Exception as e:
            print(f"Failed to fetch {source_name}: {e}")

    return all_news


if __name__ == "__main__":
    news = get_daily_news(2)
    for source, articles in news.items():
        print(f"--- {source} ---")
        for a in articles:
            print(f"  [{a['title']}]")
