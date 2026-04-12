import sys
import time
from fetchers.news_fetcher import get_daily_news
from fetchers.social_fetcher import get_social_trending
from core.script_generator import generate_podcast_script

def main():
    print("="*50)
    print("🎙️ AI Taiwan Daily Podcast 自動產製系統啟動 🎙️")
    print("="*50)
    
    # ---------------------------------------------------------
    # 階段 1：收集素材
    # ---------------------------------------------------------
    print("\n[1/3] 正在派蟲爬取台灣在地政經新聞與網路熱門話題...")
    time.sleep(1)
    
    news_data = get_daily_news(items_per_source=3)
    social_data = get_social_trending(limit_per_source=3)
    
    # 簡單印出我們收集到了幾條資料
    total_news = sum(len(articles) for articles in news_data.values())
    total_social = len(social_data)
    print(f"✔️ 成功收集到 {total_news} 篇政經焦點新聞、{total_social} 篇社群話題 (PTT/Dcard)。")

    # ---------------------------------------------------------
    # 階段 2：LLM 新聞室編輯 (生成講稿)
    # ---------------------------------------------------------
    print("\n[2/3] 將素材提交給 AI 總編輯撰寫廣播稿...")
    script = generate_podcast_script(news_data, social_data)
    
    if not script:
        print("\n生成中斷。請確認環境變數或連線後重試。")
        sys.exit(1)
        
    # ---------------------------------------------------------
    # 階段 3：半自動安全閥 (等待人類審核) -> 語音生成
    # ---------------------------------------------------------
    print("\n" + "="*50)
    print("🚨 半自動安全閥觸發：草稿已存入專案目錄下的 script.txt")
    print("👉 若您不放心，可以打開檢查是否需要微調地名拼音，或刪除不要的段落。")
    print("="*50)
    
    # 產生純人聲 MP3
    raw_voice_file = "TaiwanDaily_Podcast.mp3"
    from core.audio_builder import build_podcast_audio
    build_podcast_audio(script_file="script.txt", output_file=raw_voice_file)
    
    # 進行後製混音 (加片頭片尾配樂)
    from core.audio_mixer import mix_podcast_audio
    mix_podcast_audio(voice_file=raw_voice_file, bgm_file="bgm.mp3", output_file="TaiwanDaily_Podcast_Final.mp3")

    # ---------------------------------------------------------
    # 階段 4：內容分發 (電子報與 Threads)
    # ---------------------------------------------------------
    print("\n[4/4] 正在將內容分發至電子報與 Threads...")
    from core.content_reformatter import reformat_for_newsletter, reformat_for_threads
    
    # 1. 改寫內容
    newsletter_html = reformat_for_newsletter(script)
    threads_text = reformat_for_threads(script)
    
    # 2. 發送電子報
    from publishers.email_sender import send_newsletter
    today_date = time.strftime("%Y-%m-%d")
    send_newsletter(f"Taiwan Daily Insider - {today_date}", newsletter_html)
    
    # 3. 發布 Threads
    from publishers.threads_poster import post_to_threads
    post_to_threads(threads_text)
    
    print("\n🎉 今日所有自動化任務完成！")

if __name__ == "__main__":
    main()
