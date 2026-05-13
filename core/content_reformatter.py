import os
from google import genai
from google.genai import types

def _get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def reformat_for_newsletter(podcast_script, events_data=None):
    """
    將原版廣播口語稿，改寫成排版精美、適合人眼閱讀的 HTML 電子報格式。
    如果提供了 events_data，會在電子報最後附加一個互動式的“Today in Taiwan”活動區塊。
    """
    client = _get_gemini_client()
    if not client:
        return "<p>（無法生成電子報此內容，因為缺少 Gemini API Key）</p>"
        
    print("🤖 正在使用 AI 將廣播稿改寫為電子報 HTML 格式...")

    # 如果有事件資料，先在 Python 側組裝成 HTML，避免讓 LLM 虛構活動資訊
    events_html_block = ""
    if events_data:
        events_items = ""
        for ev in events_data:
            title   = ev.get('title', '').strip()
            summary = ev.get('summary', '').strip()
            link    = ev.get('link', '').strip()
            source  = ev.get('source', '').strip()
            if not title:
                continue
            link_tag = f' <a href="{link}" style="color:#c0392b;font-size:0.85em;">→ More info</a>' if link else ''
            events_items += (
                f'<li style="margin-bottom:10px;">'
                f'<strong>{title}</strong>{link_tag}'
                f'<br><span style="color:#555;font-size:0.9em;">{summary}</span>'
                f'<br><span style="color:#aaa;font-size:0.8em;">Source: {source}</span>'
                f'</li>'
            )
        if events_items:
            events_html_block = (
                '<hr style="margin:24px 0;">'
                '<h2 style="color:#c0392b;">&#127979; Today in Taiwan</h2>'
                f'<ul style="padding-left:18px;">{events_items}</ul>'
                '<p style="margin-top:14px;font-size:0.9em;color:#444;">'
                '💬 <strong>Know a great event happening in Taipei this week?</strong> '
                'Reply to this email and share it with us — we\'d love to highlight community tips in a future episode!'
                '</p>'
            )
    
    prompt = f"""
    You are an expert tech and business newsletter editor. I'm providing you with a script that was designed to be read out loud as a podcast.
    Your task is to convert this spoken text into a clean, highly engaging HTML newsletter format.
    
    Requirements:
    1. Output ONLY valid HTML code. Do NOT output markdown formatting like ```html.
    2. Use semantic HTML tags: <h2> for main news topics, <ul>/<li> for bullet points, <strong> for emphasis.
    3. Remove any podcast-specific filler words (like "Welcome to the show", "I'm your host", "That wraps up our episode").
    4. Start immediately with: <h1>Taiwan Daily Insider</h1><p>Here are your top updates for today:</p>.
    5. Summarize the stories slightly if the spoken text is too verbose.
    6. Tone: Professional, forward-thinking, and easy to skim.
    7. At the very end of the HTML, after all news content, insert exactly this placeholder without modification: {{EVENTS_BLOCK}}
    8. After the events block placeholder, add a short sign-off paragraph in a <p> tag that says: "Enjoyed this briefing? Forward it to a friend in Taiwan, or <a href='https://github.com/ericchi-valuation/Taiwan-Daily-Insider'>subscribe to the podcast</a> to listen on the go."
    
    Here is the podcast script:
    {podcast_script}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        html_text = response.text.replace("```html", "").replace("```", "").strip()
        # Inject the pre-built events block (safe from hallucination)
        html_text = html_text.replace("{EVENTS_BLOCK}", events_html_block)
        return html_text
    except Exception as e:
        print(f"❌ 生成電子報內容失敗: {e}")
        return f"<p>生成電子報時發生錯誤: {podcast_script[:100]}...</p>"


def reformat_for_threads(podcast_script):
    """
    將原版廣播口語稿，改寫成精簡的社群貼文短語 (Threads 版)，必須嚴格少於 500 字元。
    """
    client = _get_gemini_client()
    if not client:
        return "新一集的 Taiwan Daily Insider 上架啦！點擊主頁連結收聽最新節目🎧"

    print("🤖 正在使用 AI 萃取 Threads 貼文精華短語...")
    
    # 強化版 Prompt：強制 AI 抓出具體新聞事件
    prompt = f"""
    You are a witty, professional social media manager for a Tech and Business podcast in Taiwan.
    Read the following podcast script and create a single post for Threads.
    
    CRITICAL REQUIREMENTS:
    1. You MUST include 2 or 3 bullet points summarizing the actual news headlines from the script. Do NOT just write generic teasers. Give me the facts.
    2. STRICT FACTUALITY: Do NOT invent, hallucinate, or assume any numbers, dates, stock prices,
       exchange rates (like NTD/USD or NTD/EUR) or weather figures.
       ONLY use facts and figures EXPLICITLY stated word-for-word in the script.
       If the script does not mention a number, you MUST NOT include that number. Period.
    3. The entire output MUST be strictly UNDER 450 characters.
    4. Use 1 or 2 relevant emojis.
    5. Do NOT use HTML formatting. Use plain text and line breaks.
    6. End the post with: "Listen to the full episode on our feed! 🎧".
    7. Do not include any title like "Threads Post:". Just return the text.
    
    Here is the podcast script:
    {podcast_script}
    """

    try:
        # 使用 2.5-pro 與低溫設定確保精準
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2, 
            )
        )
        result_text = response.text.strip()
        
        # [Debug] 直接在 GitHub Log 印出來，方便我們抓蟲
        print("\n👀 [Debug] Gemini 生成的 Threads 貼文結果如下：")
        print("-" * 30)
        print(result_text)
        print("-" * 30 + "\n")
        
        return result_text
        
    except Exception as e:
        print(f"❌ 生成 Threads 貼文失敗: {e}")
        # 將備用字串加上標籤，方便我們辨識是不是出錯了
        return "[自動生成失敗] 新一集的 Taiwan Daily Insider 上線囉！點擊連結收聽最新節目🎧"