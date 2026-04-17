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
    使用 Gemini 1.5 Flash 快速為所有新聞評分 (1-10)，並依重要性排序。
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

    # 修改 Prompt：強力要求純 JSON 輸出，移除 markdown 標籤
    scoring_prompt = f"""
    You are an expert news editor. Score the following news articles from 1 to 10 based on their importance for foreign professionals and expats in Taiwan.
    
    SCORING CRITERIA:
    - 8-10: Major economic shifts (TSMC, TAIEX), key policy changes (Gold Card, visa, labor laws), major geopolitical events.
    - 5-7: Industry-specific updates, significant tech news, major cultural/infrastructure events.
    - 1-4: Minor local news, lifestyle stories, general interest.
    
    IMPORTANT: If multiple articles discuss the same topic or event, give them a "Frequency Bonus" (+1 or +2).
    
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
        # 移除 response_mime_type，避免 1.5-flash 報 404
        response = client.models.generate_content(
            model='gemini-1.5-flash-002',
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
        # 【防禦機制】就算評分失敗，也不能讓所有文章進入下一關！
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

    # Step 1: 重要性評分與排序 (取前 10 名)
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
    
    ### EDITORIAL GUIDELINES ###
    1. PRIORITIZATION: The news items are pre-sorted by an importance score. You MUST maintain this order in your broadcast, starting with the highest-scoring stories.
    2. DEPTH BY IMPORTANCE: Devote more time to higher-scoring stories. 
    3. EXPAT FOCUS: Focus heavily on business updates, tech, and macro-economics. Provide deep-dive analysis for top business segments.
    4. MUST-INCLUDE: Always include current market trends (TAIEX) and key domestic policies.
    5. FILTER TRASH: Ignore tabloid gossip.
    6. SOCIAL MEDIA: Always end the show with 1 or 2 fun topics from the "Trending in Taiwan" section. Explain local memes simply.
    7. PRONUNCIATION: Write out difficult Taiwanese names intuitively (e.g., "Tainan" -> "Tai-nan").
    8. TONE: Think "NPR Up First". Keep it fast-paced but informative.
    
    ### SCRIPT FORMAT ###
    Output ONLY a JSON object. DO NOT wrap it in ```json blocks. 
    Format:
    {{
      "script": "The full spoken broadcast script here...",
      "summary": "A concise 1-2 sentence summary here..."
    }}
    """
    
    print("\n[AI 運作中] 正在編寫講稿與摘要 (約需 20~40 秒)...")
    
    # 移除 response_mime_type，確保所有模型都能相容
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.6,
    )
    
    prompt_content = f"Here are today's materials. Please write a detailed, expansive script and a summary:\n\n{sources_text}"
    
    # 首選 2.0，若失敗則退回 1.5
    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash-002']
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
                break # 成功跳出 while
                
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ {model_name} 失敗: {error_msg}")
                
                # 真正的 429 處理邏輯：等待後「重試同一個模型」
                if "429" in error_msg or "Quota exceeded" in error_msg:
                    print(f"⏳ 偵測到 API 額度耗盡 (429)，暫停 60 秒後重試...")
                    time.sleep(60)
                    retry_count += 1
                else:
                    break # 非額度問題，跳出 while，嘗試下一個模型
                    
        if response:
            break # 成功取得回應，跳出 for 迴圈
            
    if getattr(response, 'text', None) is None:
        print("❌ 所有模型皆無回應或 API 額度受限，無法生成內容。")
        return None
        
    try:
        # 清理可能殘留的 Markdown 標籤
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