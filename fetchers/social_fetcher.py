import requests
from bs4 import BeautifulSoup
import urllib3
import feedparser

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_ptt_trending(limit=3):
    url = "https://www.ptt.cc/bbs/Gossiping/index.html"
    cookies = {'over18': '1'}
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, cookies=cookies, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        for div in soup.find_all('div', class_='r-ent')[:limit+2]:
            title_tag = div.find('div', class_='title').find('a')
            if title_tag:
                title = title_tag.text.strip()
                if '公告' not in title:
                    posts.append({
                        'title': title,
                        'url': 'https://www.ptt.cc' + title_tag['href'],
                        'topics': ['PTT Gossiping']
                    })
                    if len(posts) >= limit:
                        break
        return posts
    except Exception as e:
        print(f"Error fetching PTT: {e}")
        return []

def get_dcard_trending_bypassed(limit=3):
    """
    透過 Google News RSS 抓取 Dcard 最新熱門討論。
    這是為了完美繞過 Dcard 的 Cloudflare 防禦機制 (403 Forbidden)。
    """
    url = "https://news.google.com/rss/search?q=site:dcard.tw+when:1d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        feed = feedparser.parse(url)
        posts = []
        for entry in feed.entries[:limit]:
            # Google RSS 會把來源加在後面，例如 "租屋奇葩事 - 閒聊板 - Dcard"
            title = entry.get('title', '').replace(' - Dcard', '')
            posts.append({
                'title': title,
                'url': entry.get('link', ''),
                'topics': ['Dcard']
            })
        return posts
    except Exception as e:
        print(f"Error fetching Dcard (Bypassed): {e}")
        return []

def get_social_trending(limit_per_source=2):
    """回傳 PTT 與 Dcard 綜合熱門話題"""
    posts = []
    posts.extend(get_ptt_trending(limit=limit_per_source))
    posts.extend(get_dcard_trending_bypassed(limit=limit_per_source))
    return posts

if __name__ == "__main__":
    hot_topics = get_social_trending()
    print("--- 台灣社群熱門話題 (PTT + Dcard) ---")
    for topic in hot_topics:
        print(f"標題: {topic['title']}")
        print(f"網址: {topic['url']}\n")
