import feedparser

# 排除八卦花邊新聞的基礎黑名單 (後續 LLM 會再做第二層把關)
GOSSIP_KEYWORDS = ['偷吃', '摩鐵', '小王', '小三', '出軌', '不倫', '抓姦', '綠帽', '激戰', '走光', '露點', '豔片', '私密片', '小胖']

def is_trash_news(title, summary):
    text = title + summary
    return any(kw in text for kw in GOSSIP_KEYWORDS)

def fetch_rss_news(feed_url, limit=3):
    """抓取單一 RSS 來源的新聞"""
    feed = feedparser.parse(feed_url)
    entries = []
    
    if not feed.entries:
        return entries
        
    for entry in feed.entries:
        if len(entries) >= limit:
            break
            
        title = entry.get('title', 'No Title').strip()
        summary = entry.get('summary', '')
        
        if not title:
            continue
            
        # 爬蟲層的基礎過濾：看到花邊新聞關鍵字直接跳過
        if is_trash_news(title, summary):
            continue
            
        entries.append({
            'title': title,
            'summary': summary,
            'link': entry.get('link', '')
        })
    return entries

def get_daily_news(items_per_source=2):
    """
    獲取台灣主要新聞、商業、與運動來源
    主要客群：外籍就業金卡持卡人、外商高階主管
    """
    sources = {
        '中央社 CNA (一般要聞)': 'https://feeds.feedburner.com/cnaFirstNews',
        'Yahoo 奇摩新聞 (焦點)': 'https://tw.news.yahoo.com/rss', 
        '工商時報 (商業與財經)': 'https://news.google.com/rss/search?q=site:ctee.com.tw+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant', 
        '經濟日報 (商業與財經)': 'https://news.google.com/rss/search?q=site:money.udn.com+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant',
        '台股與外資動向 (財經深度)': 'https://news.google.com/rss/search?q=(外資+OR+台股走勢)+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant',
        '運動新聞 (台灣在地體育)': 'https://tw.news.yahoo.com/rss/sports', # 新增：體育新聞
        'Taipei Times (英文時事)': 'https://www.taipeitimes.com/xml/index.rss'
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
            print(f"[{a['title']}]")
