import os
from google import genai
from google.genai import types

def _get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

def reformat_for_newsletter(podcast_script):
    """
    將原版廣播口語稿，改寫成排版精美、適合人眼閱讀的 HTML 電子報格式。
    """
    client = _get_gemini_client()
    if not client:
        return "<p>（無法生成電子報此內容，因為缺少 Gemini API Key）</p>"
        
    print("🤖 正在使用 AI 將廣播稿改寫為電子報 HTML 格式...")
    
    prompt = f"""
    You are an expert tech and business newsletter editor. I'm providing you with a script that was designed to be read out loud as a podcast.
    Your task is to convert this spoken text into a clean, highly engaging HTML newsletter format.
    
    Requirements:
    1. Output ONLY valid HTML code. Do NOT output markdown formatting like ```html.
    2. Use semantic HTML tags: <h2> for main news topics, <ul>/<li> for bullet points, <strong> for emphasis.
    3. Remove any podcast-specific filler words (like "Welcome to the show", "I'm your host", "That wraps up our episode").
    4. Start immediately with a friendly greeting directly formatted in HTML, e.g., <h1>Taiwan Daily Insider</h1><p>Here are your top updates for today:</p>.
    5. Summarize the stories slightly if the spoken text is too verbose.
    6. Tone: Professional, forward-thinking, and easy to skim.
    
    Here is the podcast script:
    {podcast_script}
    """

    try:
         # Use the modern gemini-2.5-flash as default, fallback to gemini-2.0-flash if needed
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        # Clean up any potential markdown code blocks returned by the model
        html_text = response.text.replace("```html", "").replace("```", "").strip()
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
    
    prompt = f"""
    You are a witty, professional social media manager for a Tech and Business podcast in Taiwan.
    Read the following podcast script and extract the top 2-3 most exciting highlights to create a single post for Threads.
    
    Requirements:
    1. The output MUST be strictly UNDER 450 characters (leave some room for hashtags).
    2. Use 1 or 2 relevant emojis.
    3. Do NOT use HTML formatting. Use plain text and line breaks.
    4. End the post with a call-to-action like "Listen to the full episode on our GitHub feed or Spotify! 🎧".
    5. Do not include any title/heading like "Threads Post:". Just return the text.
    
    Here is the podcast script:
    {podcast_script}
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ 生成 Threads 貼文失敗: {e}")
        return "新一集的 Taiwan Daily Insider 上線囉！點擊連結收聽最新節目🎧"
