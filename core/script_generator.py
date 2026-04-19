import os
import json
import time
import datetime
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

    try:
        print(f"正在為 {len(all_articles)} 則新聞進行重要性評分 (熱度加權中)...")
        # ✅ 已升級為 2.5-flash，解決 404 找不到模型的問題
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=scoring_prompt
        )
        
        # 清理可能殘留的 Markdown 標籤
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        scores = json.loads(clean_text)
        
        score_map = {item['id']: item['score'] for item in scores}
        for i, a in enumerate(all_articles):
            a['score'] = score_map.get(i, 1) 
            
    except Exception as e:
        print(f"⚠️ 評分階段發生錯誤 (跳過排序): {e}")
        # 防禦機制：評分失敗時全部給 1 分，維持後續運行
        for a in all_articles:
            a['score'] = 1

    # 按分數排序並取前 10 名
    sorted_articles = sorted(all_articles, key=lambda x: x.get('score', 0), reverse=True)
    return sorted_articles[:10]


def generate_podcast_script(news_data, social_data):
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
            
    sources_text += "\n\n【Taiwan Social Media Trending (PTT / Dcard)】\n"
    for post in social_data:
        title = post.get('title', 'Unknown Topic')
        topics = post.get('topics', [])
        topics_str = ', '.join(topics) if topics else 'General'
        sources_text += f"Topic: {title} (From {topics_str})\n"

    import pytz
    tz = pytz.timezone('Asia/Taipei')
    today_str = datetime.datetime.now(tz).strftime("%B %d, %Y")

    # Step 2: AI 總編輯的 System Prompt
    system_prompt = f"""
    You are an energetic, professional yet engaging podcast host for a daily news show called "Taiwan Daily Insider". 
    Your strict target audience is foreign professionals, expats, and foreign Gold Card holders living/working in Taiwan.
    
    IMPORTANT: You MUST start the broadcast by welcoming the listener and explicitly reading today's date ({today_str}).

    ### MANDATORY SECTION — TWD/NTD CURRENCY CORNER ###
    You MUST include a dedicated "Currency Corner" segment in EVERY single broadcast, regardless of
    whether NTD news appears in today's headlines. This section is non-negotiable.
    - Report today's approximate NTD/USD and NTD/EUR exchange rates (use data from the source materials,
      or state a plausible current figure if not explicitly provided).
    - Comment briefly on the trend (strengthening, weakening, stable) and what it means practically for
      expats: e.g., remitting salary abroad, importing goods, cost of living.
    - This segment should be approximately 150-200 words long.

    ### EDITORIAL GUIDELINES ###
    1. PRIORITIZATION: The news items are pre-sorted by an importance score. You MUST maintain this order in your broadcast, starting with the highest-scoring stories.
    2. DEPTH BY IMPORTANCE: Devote significantly more time to higher-scoring stories (minimum 150 words per major story).
    3. EXPAT FOCUS: Focus heavily on business updates, tech (TSMC/semiconductor), macro-economics, and policies affecting foreigners (Gold Card, visa, labor law).
    4. FILTER TRASH: Ignore tabloid gossip and sports news unless it is a major international event.
    5. SOCIAL MEDIA: Always end the show with 1-2 fun trending topics from PTT/Dcard. Explain local memes simply in English.
    6. PRONUNCIATION: Write out difficult Taiwanese names phonetically (e.g., "Tainan" -> "Tie-nan").
    7. TONE: Think "NPR Up First". Fast-paced, insightful, and end with a smile.
    8. LENGTH: The full script MUST be between 1800 and 2400 words — this produces an 8-12 minute episode
       at natural speaking pace. Do NOT submit a script shorter than 1800 words. If you are running short,
       add more depth, context, and analysis to top stories. Do NOT add filler or repeat yourself.

    ### STRICT PROHIBITIONS ###
    - DO NOT mention the "score" or "ranking" of news items.
    - DO NOT include sports news unless it is a globally significant event (e.g., Olympics, World Cup).
    
    ### SCRIPT FORMAT ###
    Output ONLY a JSON object. DO NOT wrap it in ```json blocks. 
    Format:
    {{
      "script": "The full spoken broadcast script here...",
      "summary": "A concise 1-2 sentence summary here..."
    }}
    """
    
    print("\n[AI 運作中] 正在編寫講稿與摘要 (約需 20~40 秒)...")
    
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.6,
    )
    
    prompt_content = f"Here are today's materials. Please write a detailed, expansive script and a summary:\n\n{sources_text}"
    
    # ✅ 鎖定使用付費帳戶支援的最新系列模型
    models_to_try = ['gemini-2.5-flash', 'gemini-2.5-pro']
    response = None
    
    for model_name in models_to_try:
        retry_count = 0
        max_retries = 2
        
        while retry_count < max_retries:
            try:
                print(f"嘗試載入 {model_name} 模型...")
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
                
                # 雖然綁卡了，但仍保留防禦機制以防萬一
                if "429" in error_msg or "Quota exceeded" in error_msg:
                    print(f"⏳ 偵測到 API 額度耗盡 (429)，暫停 60 秒後重試...")
                    time.sleep(60)
                    retry_count += 1
                else:
                    break 
                    
        if response:
            break 
            
    if getattr(response, 'text', None) is None:
        print("❌ 所有模型皆無回應或 API 額度受限，無法生成內容。")
        return None
        
    try:
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
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
        print(f"❌ JSON 解析失敗: {e}\n模型回傳內容:\n{response.text[:200]}...")
        return None