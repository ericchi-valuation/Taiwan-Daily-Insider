import os
import json
from datetime import datetime, timedelta
import pytz
from podgen import Podcast, Episode, Media, Category, Person

EPISODES_FILE = "episodes.json"
FEED_FILE = "feed.xml"

# Podcast Metadata (您可以自己修改這裡的設定)
PODCAST_NAME = "Taiwan Daily Insider"
PODCAST_DESC = "Your go-to podcast for staying on top of the news that truly matters to foreign professionals, expats, and Gold Card holders right here in Taiwan. Fully automated utilizing AI."
PODCAST_WEBSITE = "https://github.com/ericchi-valuation/Taiwan-Daily-Insider"
PODCAST_EXPLICIT = False
PODCAST_IMAGE_URL = "https://raw.githubusercontent.com/ericchi-valuation/Taiwan-Daily-Insider/main/cover.png" # 之後我們會教您上傳真正的封面
AUTHOR_NAME = "Eric Chi"
AUTHOR_EMAIL = "sally0618@gmail.com"  

def generate_rss(new_title, new_summary, str_date, mp3_url, duration, file_size):
    tz = pytz.timezone('Asia/Taipei')
    
    # 1. 讀取歷史集數清單
    episodes_data = []
    if os.path.exists(EPISODES_FILE):
        with open(EPISODES_FILE, 'r', encoding='utf-8') as f:
            try:
                episodes_data = json.load(f)
            except:
                pass

    # 2. 新增今日集數
    new_ep = {
        "title": new_title,
        "summary": new_summary,
        "date": str_date,
        "mp3_url": mp3_url,
        "duration": duration,
        "file_size": file_size
    }
    
    # 檢查是否重複上架同一天
    episodes_data = [ep for ep in episodes_data if ep['title'] != new_title]
    episodes_data.append(new_ep)
    
    # 寫回 json 備份
    with open(EPISODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(episodes_data, f, ensure_ascii=False, indent=2)

    # 3. 使用 podgen 產生乾淨完美的 RSS XML
    p = Podcast()
    p.name = PODCAST_NAME
    p.description = PODCAST_DESC
    p.website = PODCAST_WEBSITE
    p.explicit = PODCAST_EXPLICIT
    p.image = PODCAST_IMAGE_URL
    p.language = "en-US"
    p.category = Category('News', 'Daily News')
    
    # 👇 更新點：加上 作者 與 Email，以符合 Spotify / Apple Podcast 驗證權限需求
    p.authors = [Person(AUTHOR_NAME, AUTHOR_EMAIL)]
    p.owner = Person(AUTHOR_NAME, AUTHOR_EMAIL)

    for ep_data in episodes_data:
        # 將 ISO 日期字串轉回 True localized datetime
        pub_date = datetime.fromisoformat(ep_data['date'])
        
        episode = Episode()
        episode.title = ep_data['title']
        episode.summary = ep_data['summary'] # Apple Podcast 需要的純文字或微量HTML簡介
        episode.publication_date = pub_date

        # 將 HH:MM:SS 轉為 datetime.timedelta
        h, m, s = map(int, ep_data['duration'].split(':'))
        td = timedelta(hours=h, minutes=m, seconds=s)
        
        episode.media = Media(ep_data['mp3_url'], int(ep_data['file_size']), type="audio/mpeg", duration=td)
        
        p.episodes.append(episode)

    p.rss_file(FEED_FILE, minimize=False)
    print(f"✅ 成功更新 RSS Feed: {FEED_FILE} (目前共 {len(episodes_data)} 集)")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--duration", required=True)
    parser.add_argument("--size", required=True)
    args = parser.parse_args()

    generate_rss(args.title, args.summary, args.date, args.url, args.duration, args.size)
