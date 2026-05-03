import os
import json
import time
import datetime
import re
import pytz
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

def score_and_sort_articles(client, news_data):
    """
    使用 Gemini 2.0 Flash 快速為所有新聞評分 (1-10)，並依重要性排序。
    """
    all_articles = []
    for source, articles in news_data.items():
        for a in articles:
            a['source_name'] = source
            all_articles.append(a)
    
    if not all_articles:
        return []

    articles_list_text = ""
    for i, a in enumerate(all_articles):
        articles_list_text += f"ID: {i} | Title: {a['title']}\nSummary: {a['summary']}\n\n"

    scoring_prompt = f"""
    You are an expert news editor for an English-language podcast targeting foreign professionals and expats in Taiwan.
    Score the following news articles from 1 to 10 based on their importance for the target audience.
    
    SCORING CRITERIA:
    - 9-10: NTD/TWD exchange rate moves, Taiwan central bank policy decisions, TAIEX major moves (>1%), TSMC earnings/capacity news, Gold Card / visa / labor law changes for foreigners.
    - 7-8: Major cross-strait political developments, significant foreign investment announcements, semiconductor industry shifts, major economic policy.
    - 5-6: Industry-specific updates, significant tech news, major infrastructure events.
    - 1-4: Minor local news, lifestyle stories, sports (unless a major international event).
    
    IMPORTANT: If multiple articles discuss the same topic or event, give them a "Frequency Bonus" (+1 or +2).
    NTD/TWD exchange rate news ALWAYS scores at least 8, even if the article seems minor.
    
    OUTPUT FORMAT:
    You MUST output ONLY a raw JSON array. DO NOT wrap it in ```json blocks. DO NOT add any conversational text.
    Example:
    [
      {{"id": 0, "score": 8}},
      {{"id": 1, "score": 5}}
    ]
    
    ARTICLES:
    {articles_list_text}
    """

    # 定義 JSON Schema
    scoring_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "id": {"type": "INTEGER"},
                "score": {"type": "INTEGER"}
            },
            "required": ["id", "score"]
        }
    }

    # 優先使用 2.5-flash，若失敗則嘗試其他模型
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.5-pro']
    response = None
    
    for model_name in models_to_try:
        try:
            print(f"正在使用 {model_name} 為 {len(all_articles)} 則新聞進行重要性評分...")
            response = client.models.generate_content(
                model=model_name,
                contents=scoring_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=scoring_schema
                )
            )
            if response:
                print(f"  ✔️ 評分完成 (使用 {model_name})")
                break
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ {model_name} 評分失敗: {error_msg}")
            if "503" in error_msg or "UNAVAILABLE" in error_msg:
                print("  ⏳ API 暫時過載 (503)，等待 15 秒後換用備援模型...")
                time.sleep(15)
            continue

    if not response:
        print("❌ 所有模型皆無法進行評分，將使用預設排序。")
        for a in all_articles:
            a['score'] = 1
        return all_articles[:10]

    try:
        if response.parsed:
            scores = response.parsed
        else:
            # 備用方案：若 parsed 為空，則嘗試手動解析
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            import re
            json_match = re.search(r'\[.*\]', clean_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(0)
            scores = json.loads(clean_text)
        
        score_map = {item['id']: item['score'] for item in scores}
        for i, a in enumerate(all_articles):
            a['score'] = score_map.get(i, 1) 
            
    except Exception as e:
        print(f"⚠️ 評分結果解析失敗: {e}")
        # 如果解析完全失敗，至少保證 score 欄位存在
        for a in all_articles:
            if 'score' not in a:
                a['score'] = 1

    # 按分數排序並取前 10 名
    sorted_articles = sorted(all_articles, key=lambda x: x.get('score', 0), reverse=True)
    return sorted_articles[:10]


def generate_podcast_script(news_data, social_data, weather_data=None, exchange_data=None, events_data=None, sponsor_text=None):
    """
    將資料送給 Gemini 進行綜合編譯，寫成英文廣播稿
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n❌ 錯誤: 找不到有效的 GEMINI_API_KEY。")
        return None

    client = genai.Client(api_key=api_key)

    if not news_data and not social_data:
        print("⚠️ 警告：沒有收集到任何新聞或社群資料，跳過 AI 生成。")
        return None

    # Step 1: 重要性評分與排序 (強制取前 10 名)
    top_articles = score_and_sort_articles(client, news_data)
    
    sources_text = "【Today's Prioritized Taiwan News Headlines】\n"
    if not top_articles:
        sources_text += "No significant news articles found today.\n"
    else:
        for a in top_articles:
            sources_text += f"\n[Score: {a.get('score', 0)}/10] Source: {a.get('source_name')} | Title: {a.get('title')}\nSummary: {a.get('summary')}\n"
            
    sources_text += "\n\n[🌤️ Today's Taipei Weather Forecast]\n"
    if weather_data and weather_data.get('condition') != 'Data unavailable':
        sources_text += (
            f"Condition: {weather_data.get('condition')}\n"
            f"High: {weather_data.get('temp_max_c')}°C / {weather_data.get('temp_max_f')}°F\n"
            f"Low: {weather_data.get('temp_min_c')}°C / {weather_data.get('temp_min_f')}°F\n"
            f"Wind: up to {weather_data.get('wind_kmh')} km/h\n"
            f"Precipitation: {weather_data.get('precip_mm')} mm\n"
        )
    else:
        sources_text += "Weather data unavailable today.\n"

    if exchange_data and exchange_data.get('usd_twd'):
        sources_text += "\n\n[💱 Today's Exchange Rates]\n"
        sources_text += f"High Volatility: {'YES' if exchange_data.get('high_volatility') else 'NO'}\n"
        sources_text += exchange_data.get('summary', '') + "\n"

    sources_text += "\n\n[💬 Taiwan Social Media Trending (PTT / Dcard)]\n"
    for post in social_data:
        title = post.get('title', 'Unknown Topic')
        topics = post.get('topics', [])
        topics_str = ', '.join(topics) if topics else 'General'
        sources_text += f"Topic: {title} (From {topics_str})\n"

    if events_data:
        sources_text += "\n\n[🎭 Today's Taipei Events]\n"
        for ev in events_data:
            sources_text += f"Event: {ev.get('title')} (Source: {ev.get('source')})\nSummary: {ev.get('summary')}\n"

    tz_str = os.environ.get("TZ", "Asia/Taipei")
    tz = pytz.timezone(tz_str)
    today_str = datetime.datetime.now(tz).strftime("%A, %B %d, %Y")

    sponsor_instruction = ""
    if sponsor_text and sponsor_text.strip():
        sponsor_instruction = f"This episode is sponsored by: {sponsor_text.strip()}."
    else:
        sponsor_instruction = "This episode has no current sponsor. Do NOT mention a sponsor."

    # Step 2: AI 總編輯的 System Prompt
    system_prompt = f"""
    You are Eric, an energetic, professional yet engaging podcast host for a daily news show called "Taiwan Daily Insider".
    Your strict target audience is foreign professionals, expats, and foreign Gold Card holders living/working in Taiwan.

    IMPORTANT: You MUST start the broadcast by welcoming the listener, introducing yourself as Eric,
    explicitly reading today's date ({today_str}), and integrating the sponsor message if provided.

    ### SPONSOR MESSAGE ###
    {sponsor_instruction}
    - If a sponsor is provided, mention it naturally early in the show.
    - If NO sponsor is provided, skip the sponsor mention entirely.

    ### MANDATORY SECTION — WEATHER BRIEFING ###
    Immediately after the opening, include a short "Taipei Weather Briefing" segment.
    - Use the weather data provided in the source materials.
    - Report the high and low temperatures in BOTH Celsius and Fahrenheit (for the diverse expat audience).
    - Mention wind and precipitation if notable.
    - Give a brief lifestyle tip (e.g., "grab an umbrella", "perfect day for a walk along the river").
    - This segment should be about 80-120 words.
    - If weather data is unavailable, say so and advise listeners to check locally.

    ### MANDATORY SECTION — SMART TWD/NTD CURRENCY CORNER ###
    You MUST include a dedicated "Currency Corner" segment in EVERY single broadcast.
    - Report the exact NTD/USD and NTD/EUR exchange rates provided in the source materials.
    - If the rates are not provided, simply mention that the data is unavailable today. DO NOT invent numbers.
    - SMART LOGIC: Check the source materials. If "High Volatility: YES" is present, you MUST provide a
      deeper analysis of the recent 1%+ swing, explaining what it means for expats' purchasing power,
      remitting salary abroad, and cost of living. If "High Volatility: NO", keep it VERY brief.
      Just state the rates and say "The Taiwan dollar is stable today." DO NOT give a long analysis if stable.

    ### EDITORIAL GUIDELINES ###
    1. PRIORITIZATION: The news items are pre-sorted by an importance score. Maintain this order.
    2. DEPTH BY IMPORTANCE: Devote significantly more time to higher-scoring stories (minimum 150 words per major story).
    3. EXPAT FOCUS: Focus heavily on business, tech (TSMC/semiconductor), macro-economics, and policies affecting foreigners.
    4. FACT-CHECKING: Do NOT say "tomorrow's announcement" if the event has already passed based on article dates.
    5. EVENTS: After the news, feature 1-2 interesting Taipei/Taiwan events from the provided sources to add "lifestyle flavor".
    6. FILTER TRASH: Ignore tabloid gossip and sports news unless a major international event.
    7. SOCIAL MEDIA: End the show with 1-2 fun trending topics from PTT/Dcard. Filter out NSFW content strictly.
    8. CALL TO ACTION (CTA): At the very end of the broadcast, before signing off, you MUST explicitly
       ask listeners to "subscribe to the podcast, share this episode with colleagues in Taiwan,
       and leave a review if you found it helpful."
    9. TONE: Think "NPR Up First". Fast-paced, insightful, and end with a smile.
    10. LENGTH: The full script MUST be between 1800 and 2400 words.

    ### STRICT PROHIBITIONS ###
    - DO NOT hallucinate or invent any news stories, quotes, or events.
    - DO NOT mention the "score" or "ranking" of news items.
    - DO NOT use rhetorical sentence fragments as transitions.
    - DO NOT use any Markdown formatting in the script.
    - DO NOT state the wrong day of the week. Today is {today_str}.

    ### SCRIPT FORMAT ###
    Output ONLY a JSON object.
    Format:
    {{
      "script": "The full spoken broadcast script here...",
      "summary": "A concise 1-2 sentence summary here..."
    }}
    """
    
    # 定義 JSON Schema
    podcast_schema = {
        "type": "OBJECT",
        "properties": {
            "script": {"type": "STRING"},
            "summary": {"type": "STRING"}
        },
        "required": ["script", "summary"]
    }

    print("\n[AI 運作中] 正在編寫講稿與摘要 (約需 20~40 秒)...")
    
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.6,
        response_mime_type='application/json',
        response_schema=podcast_schema
    )
    
    prompt_content = f"Here are today's materials. Please write a detailed, expansive script and a summary:\n\n{sources_text}"
    
    # ✅ 鎖定使用付費帳戶支援的最新系列模型
    models_to_try = [
        'gemini-2.5-flash', 
        'gemini-2.5-pro',
        'gemini-2.0-flash',
        'gemini-2.0-flash-lite',
        'gemini-3.1-flash-lite-preview'
    ]
    response = None
    
    for model_name in models_to_try:
        max_retries = 3
        base_wait = 20  # 秒，503 時的等待基數
        
        for attempt in range(max_retries):
            try:
                print(f"嘗試載入 {model_name} 模型 (attempt {attempt + 1}/{max_retries})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt_content,
                    config=config
                )
                print(f"✔️ 成功使用 {model_name} 模型生成內容！")
                break 
                
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ {model_name} 失敗: {error_msg}")
                
                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    wait_sec = base_wait * (2 ** attempt)  # 指數退避: 20s, 40s, 80s
                    print(f"  ⏳ API 暫時過載 (503)。等待 {wait_sec} 秒後重試...")
                    time.sleep(wait_sec)
                elif "429" in error_msg or "Quota exceeded" in error_msg:
                    print(f"⏳ 偵測到 API 額度耗盡 (429)，暫停 60 秒後重試...")
                    time.sleep(60)
                else:
                    break  # 非暫時性錯誤，直接換下一個模型
                    
        if response:
            break
            
    if getattr(response, 'text', None) is None:
        print("❌ 所有模型皆無回應或 API 額度受限，無法生成內容。")
        return None
        
    try:
        # 優先嘗試從 response.parsed 獲取 (如果使用了 schema)
        # 或是從 response.text 手動解析
        if getattr(response, 'parsed', None):
            result_json = response.parsed
        else:
            raw_text = response.text.strip()
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
            import re
            json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(0)
            result_json = json.loads(clean_text)
        
        script = result_json.get('script', '')
        summary = result_json.get('summary', "Today's latest news and tech updates from Taiwan.")
        
        with open("script.txt", "w", encoding="utf-8") as f:
            f.write(script)
            
        with open("summary.txt", "w", encoding="utf-8") as f:
            f.write(summary)
            
        print("✅ 講稿與摘要生成完畢！已儲存至 script.txt 與 summary.txt")
        return script
        
    except Exception as e:
        print(f"❌ JSON 解析失敗: {e}")
        print("-" * 30)
        print(f"模型原始回傳內容 (長度: {len(response.text)}):")
        print(response.text[:1000])
        print("...")
        print(response.text[-500:] if len(response.text) > 500 else "")
        print("-" * 30)
        return None

def review_and_improve_script(script: str, client=None) -> str:
    """
    AI 編輯審稿：在 TTS 之前檢查稿件品質。
    - 確認字數在 1800–2400 字之間（對應 8–12 分鐘）
    - 移除 Markdown 格式符號（#, **, *, ---）
    - 若字數不足，要求 AI 補寫至 1800 字
    - 回傳審閱後的稿件（若無問題，回傳原稿）
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not client:
        if not api_key:
            print("⚠️ [AI Editor] 無 GEMINI_API_KEY，跳過 AI 審稿，僅做格式清理。")
            return _clean_script_formatting(script)
        client = genai.Client(api_key=api_key)

    word_count = len(script.split())
    print(f"\n📝 [AI Editor] 審稿中... 目前字數: {word_count} 字")

    # ── 先做格式清理（無論 AI 是否介入）──
    script = _clean_script_formatting(script)

    needs_expansion = word_count < 1800
    needs_trim = word_count > 2600

    if not needs_expansion and not needs_trim:
        print(f"  ✔️ [AI Editor] 字數 ({word_count}) 在合理範圍內，稿件通過審閱。")
        return script

    if needs_expansion:
        action = "EXPAND"
        instruction = (
            f"The current script is only {word_count} words, which is far too short for an 8–12 minute podcast. "
            "You MUST expand it to at least 1800 words. Add deeper analysis, expat context, and historical "
            "background to each major story. Do NOT add filler, repetition, or new topics not in the original."
        )
    else:
        action = "TRIM"
        instruction = (
            f"The current script is {word_count} words, which is slightly long. "
            "Trim it to under 2400 words by cutting redundant sentences, but keep all main stories intact."
        )

    print(f"  🤖 [AI Editor] 正在 {action} 稿件...")

    editor_prompt = f"""
    You are a senior podcast editor for "Taiwan Daily Insider", an English-language daily news podcast.

    {instruction}

    STRICT RULES:
    1. Output ONLY the revised script text. No JSON, no markdown, no explanation.
    2. Do NOT add any Markdown formatting (no #, ##, **, *, ---).
    3. Do NOT add vocabulary lessons or "word of the day" segments.
    4. Do NOT invent new facts, numbers, or events.
    5. Maintain the same host voice and NPR-style tone.
    6. Keep the opening greeting intact.

    HERE IS THE CURRENT SCRIPT:
    ---
    {script}
    ---
    """

    editor_models = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.5-pro']
    for model_name in editor_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=editor_prompt,
                config=types.GenerateContentConfig(temperature=0.4)
            )
            revised = _clean_script_formatting(response.text.strip())
            new_word_count = len(revised.split())
            print(f"  ✔️ [AI Editor] 審稿完成 (使用 {model_name})，修訂後字數: {new_word_count} 字")
            return revised
        except Exception as e:
            print(f"  ⚠️ [AI Editor] {model_name} 失敗: {e}")
            time.sleep(15)

    print("  ⚠️ [AI Editor] 所有模型均失敗，回傳格式清理後的原稿。")
    return script


def _clean_script_formatting(script: str) -> str:
    """
    移除 TTS 不友好的格式符號：Markdown 標題、粗體、分隔線等。
    """
    # 移除 Markdown 標題 (# / ## / ###)
    script = re.sub(r'^#{1,6}\s+', '', script, flags=re.MULTILINE)
    # 移除粗體/斜體 (**text** 或 *text*)
    script = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', script)
    # 移除水平分隔線 (--- / *** / ___)
    script = re.sub(r'^[\-\*_]{3,}\s*$', '', script, flags=re.MULTILINE)
    # 清理多餘的空行
    script = re.sub(r'\n{3,}', '\n\n', script)
    return script.strip()