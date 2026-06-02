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


def diagnostic_list_models(client):
    """
    [自動診斷工具] 查詢這把 API Key 到底可以使用哪些模型。
    預設靜默 — 僅在 .env 設定 DEBUG_MODELS=true 時才輸出。
    """
    if os.environ.get("DEBUG_MODELS", "").strip().lower() not in ("1", "true", "yes"):
        return  # 靜默模式：正常 pipeline 不印出模型清單

    print("\n🔍 [系統診斷] 正在向 Google 查詢此 API Key 可用的模型清單...")
    try:
        models = client.models.list()
        available_models = []
        for m in models:
            if 'generateContent' in m.supported_actions:
                clean_name = m.name.replace('models/', '')
                available_models.append(clean_name)
        
        if available_models:
            print(f"✅ 您的 API Key 支援以下 {len(available_models)} 個模型：")
            print(", ".join(available_models))
        else:
            print("❌ 警告：您的 API Key 無法存取任何文字生成模型！這通常是因為帳號權限或地區限制 (歐盟區)。")
            
    except Exception as e:
        print(f"❌ 查詢模型清單失敗，您的金鑰或連線被阻擋: {e}")
    print("-" * 50 + "\n")


def score_and_sort_articles(client, news_data):
    """
    使用 Gemini 評分模型快速為所有新聞評分 (1-10)，並依重要性排序。
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

    # 評分用的備援模型清單
    models_to_try = ['gemini-2.5-flash', 'gemini-3.5-flash', 'gemini-2.5-flash-lite']
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
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            json_match = re.search(r'\[.*\]', clean_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(0)
            scores = json.loads(clean_text)
        
        score_map = {item['id']: item['score'] for item in scores}
        for i, a in enumerate(all_articles):
            a['score'] = score_map.get(i, 1) 
            
    except Exception as e:
        print(f"⚠️ 評分結果解析失敗: {e}")
        for a in all_articles:
            if 'score' not in a:
                a['score'] = 1

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
    
    diagnostic_list_models(client)

    if not news_data and not social_data:
        print("⚠️ 警告：沒有收集到任何新聞或社群資料，跳過 AI 生成。")
        return None

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
    - Give ONE brief, practical lifestyle tip ONLY (e.g., "grab an umbrella" or "a light jacket will do"). Do NOT suggest specific locations or leisure activities. One sentence maximum.
    - This segment should be about 80–120 words total.
    - If weather data is unavailable, say so and advise listeners to check locally.

    ### MANDATORY SECTION — SMART TWD/NTD CURRENCY CORNER ###
    You MUST include a dedicated "Currency Corner" segment in EVERY single broadcast.
    - CRITICAL TIMING CONTEXT: The exchange rates provided come from the API's 'latest' endpoint,
      which reflects the MOST RECENTLY SETTLED trading day's closing rates (typically yesterday).
      Therefore, NEVER say "Today's exchange rate is" or "Today, the Taiwan dollar...".
      Instead, you MUST frame it accurately, for example: "Yesterday, the Taiwan dollar was...", or
      "As of yesterday's close, the exchange rate held steady at...", or "As of the last market close...".
    - Report the exact TWD/USD and TWD/EUR exchange rates provided in the source materials.
    - If the rates are not provided, simply mention that the data is unavailable. DO NOT invent numbers.
    - SMART LOGIC — STRICT WORD LIMITS:
      * If "High Volatility: YES" is present: provide deeper analysis (100–150 words) explaining what
        the 1%+ swing means for expats — purchasing power, remitting salary abroad, cost of living.
      * If "High Volatility: NO": the ENTIRE Currency Corner segment MUST be 40 words or fewer.
        HARD LIMIT — do NOT exceed 40 words. Do NOT explain "why stability matters", do NOT add
        historical context, do NOT discuss purchasing power. Simply state the two rates and close.
        Example of correct low-volatility output (≈35 words):
        "As of yesterday's close, the Taiwan dollar was stable. One US dollar bought 31.36 TWD,
        and one Euro fetched 36.52 TWD. No significant moves to report — good news for your wallet."

    ### EDITORIAL GUIDELINES ###
    1. PRIORITIZATION: The news items are pre-sorted by an importance score. Maintain this order.
    2. DEPTH BY IMPORTANCE: Devote more time to higher-scoring stories, but cap any single story at
       ~300 words maximum so that multiple topics always get covered.
    3. TOPIC DIVERSITY — CRITICAL: This is a DAILY NEWS show, not a company analysis report.
       Aim to cover at least 3-4 distinct topics per episode.
       - TSMC / semiconductor news: NO MORE THAN 25% of the total script word count, even if
         TSMC-related articles dominate today's headlines. Once you hit the cap, move on.
       - If TSMC news is the only major story available, summarize it concisely and pivot to macro
         economy, labor policy, social trends, or lifestyle to fill the remaining time.
       - DO NOT expand a single company's story with historical background, deep-dive analysis,
         or multi-paragraph technical explanations just to fill word count.
    4. EXPAT FOCUS: Cover a balanced mix — business, macro-economics, labor/visa policy, lifestyle,
       and tech. Tech (TSMC/semiconductor) is one pillar, not the whole show.
    5. FACT-CHECKING: Do NOT say "tomorrow's announcement" if the event has already passed based on article dates.
    6. EVENTS: After the news, feature 1-2 interesting Taipei/Taiwan events from the provided sources to add "lifestyle flavor".
    7. FILTER TRASH: Ignore tabloid gossip and sports news unless a major international event.
    8. SOCIAL MEDIA: End the news section with 1-2 fun trending topics from PTT/Dcard. Filter out NSFW content strictly.
    9. CALL TO ACTION (CTA): MANDATORY. After the social media segment, you MUST say: "That's all for today's Taiwan Daily Insider. If you found this episode helpful, please subscribe, share it with colleagues and friends here in Taiwan, and drop us a review wherever you listen — it truly helps us grow. I'm Eric, and I'll see you tomorrow. Zai Jian!" This closing MUST be the very last thing in the script. The script is NOT complete without it.
    10. TONE: Think "NPR Up First". Fast-paced, insightful, and end with a smile.
    11. LENGTH: The full script MUST be between 1800 and 2400 words. ALWAYS finish the full closing before hitting the word limit — never truncate the CTA or sign-off.
    12. POLITICAL TITLES — CRITICAL FACT-CHECK RULE: NEVER assume or repeat a person's political title
        from your training data or memory. ONLY use titles (e.g. "President", "Minister")
        that are EXPLICITLY stated in TODAY's provided source materials.

    ### STRICT PROHIBITIONS ###
    - DO NOT hallucinate or invent any news stories, quotes, or events.
    - DO NOT mention any editorial score or rating in the spoken script.
    - DO NOT use rhetorical sentence fragments as transitions.
    - DO NOT use any Markdown formatting in the script.
    - DO NOT state the wrong day of the week. Today is {today_str}.
    - DO NOT list or enumerate the target audience by name in the script. Phrases like "foreign professionals, expats, and Gold Card holders making Taiwan their home" or any similar enumeration of listener types are BANNED. Speak directly to the listener as "you" instead.
    - DO NOT let any single company (e.g. TSMC, Nvidia, Hon Hai) or single topic exceed 25% of the
      total script. If you have already devoted ~500 words to TSMC, STOP and move to the next story.
    - DO NOT pad a story with historical background or technical deep-dives to reach the word count.
      Instead, use that space to cover more distinct news topics.

    ### SCRIPT FORMAT ###
    Output ONLY a JSON object.
    Format:
    {{
      "script": "The full spoken broadcast script ending with the mandatory CTA and Zai Jian sign-off...",
      "summary": "A 3-5 sentence episode description for podcast platforms. Start with today's top 2-3 news stories, then list today's Taipei events with their names and a one-line description each. End with one sentence inviting listeners to tune in."
    }}
    """
    
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
    
    models_to_try = [
        'gemini-2.5-flash', 
        'gemini-3.5-flash',
        'gemini-2.5-pro',
        'gemini-2.5-flash-lite'
    ]
    response = None
    
    for model_name in models_to_try:
        max_retries = 3
        base_wait = 20  
        
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
                    wait_sec = base_wait * (2 ** attempt) 
                    print(f"  ⏳ API 暫時過載 (503)。等待 {wait_sec} 秒後重試...")
                    time.sleep(wait_sec)
                elif "429" in error_msg or "Quota exceeded" in error_msg:
                    print(f"⏳ 偵測到 API 額度耗盡 (429)，暫停 60 秒後重試...")
                    time.sleep(60)
                else:
                    break 
                    
        if response:
            break
            
    if getattr(response, 'text', None) is None:
        print("❌ 所有模型皆無回應或 API 額度受限，無法生成內容。")
        return None
        
    try:
        if getattr(response, 'parsed', None):
            result_json = response.parsed
        else:
            raw_text = response.text.strip()
            clean_text = raw_text.replace("```json", "").replace("```", "").strip()
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
            "You MUST expand it to between 1800 and 2200 words. Add deeper analysis, expat context, and historical "
            "background to each major story. Do NOT add filler, repetition, or new topics not in the original. "
            "CRITICAL: Do NOT exceed 2200 words under any circumstances."
        )
    else:
        action = "TRIM"
        instruction = (
            f"The current script is {word_count} words, which is slightly long. "
            "Trim it to under 2400 words by cutting redundant sentences, but keep all main stories and the closing intact."
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
    6. CRITICAL: The script MUST end with the full closing CTA and "Zai Jian!" sign-off. If the original script is missing this or it is cut off, you MUST restore it: add "That's all for today's Taiwan Daily Insider. If you found this episode helpful, please subscribe, share it with colleagues and friends here in Taiwan, and drop us a review wherever you listen — it truly helps us grow. I'm Eric, and I'll see you tomorrow. Zai Jian!"
    7. When trimming, NEVER cut the closing CTA or sign-off — trim from the middle of news stories instead.
    8. DO NOT list or enumerate the target audience by name anywhere in the script. Remove any phrases like "foreign professionals, expats, and Gold Card holders making Taiwan their home" — replace them with direct address to the listener ("you").
    9. For weather tips: keep only ONE brief practical tip (e.g. "grab an umbrella"). Remove any suggestions of specific venues, parks, or leisure activities.
    10. CURRENCY CORNER HARD LIMIT: If the exchange rate data shows Low Volatility (change < 1%), the
        Currency Corner segment MUST be 40 words or fewer. If it is longer, trim it down ruthlessly.
        Keep only the two rates and one closing sentence. Remove ALL analysis, historical context,
        purchasing-power explanations, and economic commentary from it.

    HERE IS THE CURRENT SCRIPT:
    ---
    {script}
    ---
    """

    editor_models = ['gemini-2.5-flash', 'gemini-3.5-flash', 'gemini-2.5-pro']
    revised = None
    used_model = None
    for model_name in editor_models:
        max_editor_retries = 2  # 同一個模型最多重試 2 次 (針對 503)
        for editor_attempt in range(1, max_editor_retries + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=editor_prompt,
                    config=types.GenerateContentConfig(temperature=0.4)
                )
                revised = _clean_script_formatting(response.text.strip())
                used_model = model_name
                new_word_count = len(revised.split())
                print(f"  ✔️ [AI Editor] 審稿完成 (使用 {model_name})，修訂後字數: {new_word_count} 字")
                break  # 成功，跳出 retry loop
            except Exception as e:
                error_msg = str(e)
                is_overload = "503" in error_msg or "UNAVAILABLE" in error_msg
                if is_overload and editor_attempt < max_editor_retries:
                    wait_sec = 15 * editor_attempt  # 第1次等15s, 第2次等30s
                    print(f"  ⚠️ [AI Editor] {model_name} 503 過載 (attempt {editor_attempt}/{max_editor_retries})，等待 {wait_sec} 秒後重試...")
                    time.sleep(wait_sec)
                else:
                    print(f"  ⚠️ [AI Editor] {model_name} 失敗: {e}")
                    if not is_overload:
                        break  # 非 503 錯誤 (如 400) 不重試，直接跳下一個模型
                    time.sleep(10)
        if revised:
            break  # 已有結果，跳出模型循璴

    if revised is None:
        print("  ⚠️ [AI Editor] 所有模型均失敗，回傳格式清理後的原稿。")
        return script

    # ── Second-pass trim: if expansion overshot the 2400-word target, trim it ─
    post_edit_count = len(revised.split())
    if needs_expansion and post_edit_count > 2600:
        print(f"  ⚠️ [AI Editor] 展開後字數 ({post_edit_count}) 超過上限 2600，啟動第二輪自動裁剪...")
        trim_instruction = (
            f"The current script is {post_edit_count} words, which is too long for a 10-minute podcast. "
            "Trim it to under 2400 words by removing redundant sentences and over-explained passages, "
            "but keep ALL main stories, the weather briefing, currency corner, events, and the full closing CTA intact."
        )
        trim_prompt = f"""
    You are a senior podcast editor for "Taiwan Daily Insider", an English-language daily news podcast.

    {trim_instruction}

    STRICT RULES:
    1. Output ONLY the revised script text. No JSON, no markdown, no explanation.
    2. Do NOT add any Markdown formatting (no #, ##, **, *, ---).
    3. NEVER cut the closing CTA or "Zai Jian!" sign-off — trim from the middle of news stories instead.
    4. Maintain the same host voice and NPR-style tone.

    HERE IS THE CURRENT SCRIPT:
    ---
    {revised}
    ---
    """
        for model_name in editor_models:
            try:
                resp2 = client.models.generate_content(
                    model=model_name,
                    contents=trim_prompt,
                    config=types.GenerateContentConfig(temperature=0.3)
                )
                trimmed = _clean_script_formatting(resp2.text.strip())
                final_count = len(trimmed.split())
                print(f"  ✔️ [AI Editor] 第二輪裁剪完成 (使用 {model_name})，最終字數: {final_count} 字")
                return trimmed
            except Exception as e:
                print(f"  ⚠️ [AI Editor] 第二輪裁剪失敗 ({model_name}): {e}")
                time.sleep(10)
        print("  ⚠️ [AI Editor] 第二輪裁剪所有模型均失敗，使用第一輪結果。")

    return revised


def _clean_script_formatting(script: str) -> str:
    """
    移除 TTS 不友好的格式符號：Markdown 標題、粗體、分隔線等。
    同時移除任何意外流入播報稿的編輯評分語句。
    """
    script = re.sub(r'^#{1,6}\s+', '', script, flags=re.MULTILINE)
    script = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', script)
    script = re.sub(r'^[\-\*_]{3,}\s*$', '', script, flags=re.MULTILINE)
    script = re.sub(
        r'(?i)(,?\s*)'
        r'((?:both|also|each)?\s*(?:scoring|rated?|with\s+a\s+score\s+of|a\s+perfect)'
        r'\s+[a-z\s]*?\d{1,2}(?:\s*out\s*of\s*10|/10))',
        '',
        script
    )
    script = re.sub(r'\n{3,}', '\n\n', script)
    return script.strip()