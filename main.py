import os
import sys
import time
import datetime
import pytz

from core.content_reformatter import reformat_for_newsletter, reformat_for_threads


def verify_environment():
    """
    Check if all required environment variables are set.
    Prints a warning if any are missing but does NOT abort the pipeline.
    """
    required_keys = [
        "GEMINI_API_KEY",
        "ELEVENLABS_API_KEY",
        "GMAIL_ADDRESS",
        "GMAIL_APP_PASSWORD",
        "THREADS_USER_ID",
        "THREADS_ACCESS_TOKEN"
    ]
    missing = [key for key in required_keys if not os.getenv(key)]

    print("\n🔍 [Health Check] Verifying environment variables...")
    if missing:
        print(f"  ⚠️  Missing optional/required keys: {', '.join(missing)}")
        print("  (Pipeline will proceed but some steps may fail or fallback to free tiers)\n")
    else:
        print("  ✅ All environment variables are set.\n")


def main():
    from fetchers.news_fetcher import get_daily_news
    from fetchers.social_fetcher import get_social_trending
    from fetchers.weather_fetcher import get_taipei_weather
    from fetchers.exchange_rate_fetcher import get_exchange_rates
    from fetchers.events_fetcher import get_taipei_events
    from core.script_generator import generate_podcast_script, review_and_improve_script

    verify_environment()

    tz_str = os.environ.get("TZ", "Asia/Taipei")
    tz = pytz.timezone(tz_str)
    today_str = datetime.datetime.now(tz).strftime("%B %d, %Y")

    print("=" * 50)
    print(f"🎙️  Taiwan Daily Insider — Pipeline starting for {today_str}")
    print("=" * 50)

    # ── Step 1: Fetch all data ──────────────────────────────────────────────
    print("\n📡 Step 1/5: Fetching latest Taiwan news...")
    news_data = get_daily_news(items_per_source=3)
    total_news = sum(len(a) for a in news_data.values())
    print(f"  ✔️ Collected {total_news} articles from {len(news_data)} sources.")

    print("\n🌤️  Step 1b: Fetching Taipei weather...")
    weather_data = get_taipei_weather()

    print("\n💱  Step 1c: Fetching Exchange Rates...")
    exchange_data = get_exchange_rates()

    print("\n💬 Step 1d: Fetching social trending topics...")
    social_data = get_social_trending(limit_per_source=3)
    print(f"  ✔️ Collected {len(social_data)} social trending posts.")

    print("\n🎭 Step 1e: Fetching Taipei events...")
    events_data = get_taipei_events(limit=2)

    # ── Step 1f: Read Sponsor Text ──────────────────────────────────────────
    sponsor_text = None
    if os.path.exists("sponsor.txt"):
        try:
            with open("sponsor.txt", "r", encoding="utf-8") as f:
                sponsor_text = f.read().strip()
            if sponsor_text:
                print(f"  ✔️  Sponsor text detected: '{sponsor_text[:40]}...'")
        except Exception as e:
            print(f"  ⚠️  Could not read sponsor.txt: {e}")

    # ── Step 2: Generate AI podcast script ─────────────────────────────────
    print("\n🤖 Step 2/5: Generating AI podcast script...")
    script = generate_podcast_script(
        news_data,
        social_data,
        weather_data,
        exchange_data,
        events_data=events_data,
        sponsor_text=sponsor_text
    )

    if not script:
        print("❌ Script generation failed. Aborting pipeline.")
        sys.exit(1)

    print(f"  ✔️ Script generated ({len(script.split())} words).")

    print("\n📝 Step 2b/5: AI Editor reviewing script before TTS...")
    script = review_and_improve_script(script)

    with open("script.txt", "w", encoding="utf-8") as f:
        f.write(script)
    print(f"  ✔️ Final script saved ({len(script.split())} words). Ready for TTS.")

    # ── Step 3: Build TTS audio ─────────────────────────────────────────────
    print("\n🎤 Step 3/5: Generating TTS audio from script...")
    raw_voice_file = "TaiwanDaily_Podcast.mp3"
    final_file     = "TaiwanDaily_Podcast_Final.mp3"
    bgm_file       = "bgm.mp3"

    from core.audio_builder import build_podcast_audio
    build_podcast_audio(script_file="script.txt", output_file=raw_voice_file)

    if not os.path.exists(raw_voice_file) or os.path.getsize(raw_voice_file) == 0:
        print("❌ TTS audio not generated. Aborting pipeline.")
        sys.exit(1)
    print(f"  ✔️ Raw voice audio ready: {raw_voice_file}")

    # ── Step 4: Mix BGM with voice ──────────────────────────────────────────
    print("\n🎵 Step 4/5: Mixing BGM with voice...")
    from core.audio_mixer import mix_podcast_audio
    if os.path.exists(bgm_file):
        try:
            mix_podcast_audio(voice_file=raw_voice_file, bgm_file=bgm_file, output_file=final_file)
            print(f"  ✔️ Final mixed podcast ready: {final_file}")
        except Exception as e:
            print(f"  ⚠️ Mixing failed ({e}). Falling back to voice-only file.")
            import shutil
            shutil.copy(raw_voice_file, final_file)
    else:
        print(f"  ⚠️ BGM file '{bgm_file}' not found. Using voice-only output.")
        import shutil
        shutil.copy(raw_voice_file, final_file)

    # ── Step 5: Publish ─────────────────────────────────────────────────────
    print("\n📢 Step 5/5: Publishing content...")

    # 5a. Newsletter
    try:
        with open("script.txt", "r", encoding="utf-8") as f:
            script_text = f.read()
        html_content = reformat_for_newsletter(script_text)
        from publishers.email_sender import send_newsletter
        send_newsletter(f"Taiwan Daily Insider — {today_str}", html_content)
    except Exception as e:
        print(f"  ⚠️ Newsletter step failed: {e}")

    # 5b. Threads
    try:
        with open("script.txt", "r", encoding="utf-8") as f:
            script_text = f.read()
        threads_post = reformat_for_threads(script_text)
        print(f"\n👀 [Debug] Threads post:\n{threads_post}\n" + "-" * 30)
        from publishers.threads_poster import post_to_threads
        post_to_threads(threads_post)
    except Exception as e:
        print(f"  ⚠️ Threads step failed: {e}")

    print("\n" + "=" * 50)
    print(f"✅ Pipeline complete! '{final_file}' is ready for upload.")
    print("=" * 50)


if __name__ == "__main__":
    main()