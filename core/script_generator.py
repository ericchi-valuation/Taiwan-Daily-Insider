import os
import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 載入環境變數 (讀取 .env 中的 API key)
load_dotenv()

def generate_podcast_script(news_data, social_data):
    """
    將爬蟲收集到的原始新聞與社群資料，送給 Gemini 進行綜合編譯，寫成英文廣播稿
    (已升級至最新版 google.genai SDK)
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n❌ 錯誤: 找不到有效的 GEMINI_API_KEY。")
        print("請在專案目錄 `.env` 檔案中加入： GEMINI_API_KEY=您在_Google_AI_Studio_申請的_API_KEY")
        return None

    # 初始化全新的 Gemini Client
    client = genai.Client(api_key=api_key)

    # Step 1: 將資料整理成具有結構的文字餵給 AI
    sources_text = "【Today's Taiwan News Headlines】\n"
    for source, articles in news_data.items():
        sources_text += f"\n--- Source: {source} ---\n"
        for a in articles:
            sources_text += f"Title: {a['title']}\nSummary: {a['summary']}\n"
            
    sources_text += "\n\n【Taiwan Social Media Trending (PTT / Dcard)】\n"
    for post in social_data:
        sources_text += f"Topic: {post['title']} (From {', '.join(post['topics'])})\n"

    today_str = datetime.date.today().strftime("%B %d, %Y")

    # Step 2: AI 總編輯的 System Prompt (靈魂核心)
    system_prompt = f"""
    You are an energetic, professional yet engaging podcast host for a daily news show called "Taiwan Daily Insider". 
    Your strict target audience is foreign professionals, expats, and foreign Gold Card holders living/working in Taiwan.
    
    IMPORTANT: You MUST start the broadcast by welcoming the listener and explicitly reading today's date ({today_str}).
    
    Your job is to read the provided daily news headlines and social media topics from Taiwan, and synthesize them into a cohesive, highly engaging English podcast script.
    
    ### EDITORIAL GUIDELINES ###
    1. SYNTHESIS, NOT TRANSLATION: Do not just dryly translate the news. Connect the dots. Group related stories (e.g. "On the business front...", "In weather..."). Pick only the most impactful 6-8 stories.
    2. EXPAT FOCUS AND DEEP DIVE: Focus heavily on business updates, tech/semiconductor news, macro-economics, Taiwan stock market trends (TAIEX), and foreign investments. Provide deeper, expanded analysis for the stock market and business segments to add value to professionals. Do not rush through business headlines.
    3. FILTER TRASH: Completely ignore any remaining tabloid gossip, petty crimes, or overly sensational local incidents. If any made it past the initial filters, you MUST drop them.
    4. SOCIAL MEDIA SEGMENT: Always end the show with a fun "Trending in Taiwan" segment. Pick 1 or 2 quirky/fun topics from the PTT/Dcard list to help expats understand local Taiwanese internet culture and memes. Explain the context simply.
    5. PRONUNCIATION SAFEGUARDS: Write out difficult Taiwanese names or locations intuitively so a generic English Text-to-Speech (TTS) voice engine won't butcher them. 
       - For example, if mentioning "Tainan", write it as "Tai-nan". For "Hsinchu", write "Hsin-choo".
    6. TONE: Think "NPR Up First" combined with "The Daily". Keep it fast-paced, informative, and wrap up with a smile.
    
    ### SCRIPT FORMAT ###
    - Output ONLY the spoken words. 
    - DO NOT output any stage directions like [Intro Music] or [Outro Music].
    - DO NOT output any Markdown tags like bold (**), italics (*), or brackets ([]). The text goes directly into a Text-to-Speech Engine.
    - Write in a natural, conversational spoken English rhythm. Use short sentences but elaborate on complex business topics.
    - The target length is around 1800 to 2200 words (which translates to roughly 10-12 minutes of speaking). Do not cut corners; be detailed.
    """
    
    print("\n[AI 運作中] 正在綜合各方新聞，並利用最新版 Gemini 為金卡持卡人撰寫高階廣播稿 (約需 20~40 秒)...")
    
    try:
        # 使用最新的 genai_config
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.6,
        )
        
        prompt_content = f"Here are today's materials. Please write the script:\n\n{sources_text}"
        
        # 實作多模型 Fallback (備用支援) 以防止某些型號無免費額度 (429 limit: 0) 或 404
        models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
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
            except Exception as inner_e:
                print(f"⚠️ {model_name} 拒絕請求或失敗: {inner_e}")
                continue
                
        if not response:
            print("❌ 所有模型皆無回應，請確認 API 狀態。")
            return None
            
        script = response.text
        
        # 將生肉講稿存檔，保留「半自動」的安全閥，等使用者確認
        with open("script.txt", "w", encoding="utf-8") as f:
            f.write(script)
            
        print("✅ 講稿生成完畢！已將草稿儲存至專案目錄下的 script.txt")
        return script
        
    except Exception as e:
        print(f"\n❌ Gemini LLM 生成發生致命錯誤: {e}")
        return None

if __name__ == "__main__":
    print("此模組為函式庫，請透過 main.py 來執行。")
