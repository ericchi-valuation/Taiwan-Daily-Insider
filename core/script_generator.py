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
    考慮因素：主題重要性、重複出現程度 (Mention degree)。
    """
    all_articles = []
    for source, articles in news_data.items():
        for a in articles:
            a['source_name'] = source
            all_articles.append(a)
    
    if not all_articles:
        return []

    # 準備評分用的 Text
    articles_list_text = ""
    for i, a in enumerate(all_articles):
        articles_list_text += f"ID: {i} | Title: {a['title']}\nSummary: {a['summary']}\n\n"

    scoring_prompt = f"""
    You are an expert news editor. Your task is to score the following news articles from 1 to 10 based on their importance for foreign professionals and expats in Taiwan.
    
    SCORING CRITERIA:
    - 8-10: Major economic shifts (TSMC, TAIEX), key policy changes (Gold Card, visa, labor laws), major geopolitical events.
    - 5-7: Industry-specific updates, significant tech news, major cultural/infrastructure events.
    - 1-4: Minor local news, lifestyle stories, general interest.
    
    IMPORTANT: If multiple articles discuss the same topic or event, give them a "Frequency Bonus" (+1 or +2) because it indicates a hot topic.
    
    OUTPUT FORMAT:
    Provide only a JSON list of objects with "id" and "score", like this:
    [{"id": 0, "score": 8}, {"id": 1, "score": 5}, ...]
    
    ARTICLES:
    {articles_list_text}
    """

    try:
        print(f"正在為 {len(all_articles)} 則新聞進行重要性評分 (熱度加權中)...")
        # 使用 Flash 模型進行快速評分
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=scoring_prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
            )
        )
        scores = json.loads(response.text)
        
        # 將分數寫回原資料
        score_map = {item['id']: item['score'] for item in scores}
        for i, a in enumerate(all_articles):
            a['score'] = score_map.get(i, 1) # 預設最低分
            
    except Exception as e:
        print(f"⚠️ 評分階段發生錯誤 (跳過排序): {e}")
        # 如果評分失敗，給予預設分數以維持後續運行
        for a in all_articles:
            a['score'] = 1

    # 按分數排序並取前 10 名
    sorted_articles = sorted(all_articles, key=lambda x: x.get('score', 0), reverse=True)
    return sorted_articles[:10]

def generate_podcast_script(news_data, social_data):
    """
    將爬蟲收集到的原始新聞與社群資料，送給 Gemini 進行綜合編譯，寫成英文廣播稿
    (已加入重要性評分排序與防呆機制)
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n❌ 錯誤: 找不到有效的 GEMINI_API_KEY。")
        return None

    client = genai.Client(api_key=api_key)

    # 防呆：如果根本沒有傳入資料，提早結束，節省 API 費用
    if not news_data and not social_data:
        print("⚠️ 警告：沒有收集到任何新聞或社群資料，跳過 AI 生成。")
        return None

    # Step 1: 重要性評分與排序 (取前 10 名)
    top_articles = score_and_sort_articles(client, news_data)
    
    # 重新組裝 sources_text，包含分數供 AI 參考
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

    today_str = datetime.date.today().strftime("%B %d, %Y")

    # Step 2: AI 總編輯的 System Prompt
    system_prompt = f"""
    You are an energetic, professional yet engaging podcast host for a daily news show called "Taiwan Daily Insider". 
    Your strict target audience is foreign professionals, expats, and foreign Gold Card holders living/working in Taiwan.
    
    IMPORTANT: You MUST start the broadcast by welcoming the listener and explicitly reading today's date ({today_str}).
    
    ### EDITORIAL GUIDELINES ###
    1. PRIORITIZATION: The news items are pre-sorted by an importance score (1-10). You MUST maintain this order in your broadcast, starting with the highest-scoring stories to capture the audience's attention immediately.
    2. DEPTH BY IMPORTANCE: Devote more time and detail to higher-scoring stories. Low-scoring stories should be mentioned briefly as part of a roundup.
    3. EXPAT FOCUS: Focus heavily on business updates, tech, and macro-economics. You MUST provide deep-dive analysis for the top business segments.
    4. MUST-INCLUDE: Always include current market trends (TAIEX) and key domestic policies, but scale their length based on their relative importance score.
    5. FILTER TRASH: Ignore tabloid gossip or petty crimes.
    6. SOCIAL MEDIA SEGMENT: Always end the show with 1 or 2 fun topics from the "Trending in Taiwan" section. Explain local memes simply.
    7. PRONUNCIATION SAFEGUARDS: Write out difficult Taiwanese names intuitively (e.g., "Tainan" -> "Tai-nan").
    8. TONE: Think "NPR Up First". Keep it fast-paced but informative.
    
    ### SCRIPT FORMAT ###
    - Output ONLY the spoken words. No stage directions ([Intro Music]). No Markdown (**).
    - Write in a natural spoken English rhythm.
    - Elaborate extensively on high-scoring stories to ensure the script is sufficiently long and detailed.
    """
    
    print("\n[AI 運作中] 正在編寫講稿 (約需 20~40 秒)...")
    
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.6,
    )
    
    prompt_content = f"Here are today's materials. Please write a detailed, expansive script:\n\n{sources_text}"
    
    # 移除了不存在的 2.5，專注於 2.0 與穩定的 1.5 系列
    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']
    response = None
    
    for model_name in models_to_try:
        try:
            print(f"嘗試載入 {model_name} 模型...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt_content,
                config=config
            )
            print(f"✔️ 成功使用 {model_name} 模型生成講稿！")
            break
            
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ {model_name} 失敗: {error_msg}")
            
            # 針對 429 額度耗盡進行特殊處理
            if "429" in error_msg or "Quota exceeded" in error_msg:
                print("⏳ 偵測到 API 額度耗盡 (429)，等待 60 秒後重試...")
                time.sleep(60)
                # 這裡設計為直接跳出迴圈，因為如果免費額度沒了，換模型也沒用，需等待
                break 
            continue
            
    if getattr(response, 'text', None) is None:
        print("❌ 所有模型皆無回應或 API 額度受限，無法生成講稿。")
        return None
        
    script = response.text
    
    with open("script.txt", "w", encoding="utf-8") as f:
        f.write(script)
        
    print("✅ 講稿生成完畢！已將草稿儲存至 script.txt")
    return script