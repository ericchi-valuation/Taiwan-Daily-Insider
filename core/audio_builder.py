import os
import requests
import asyncio
from dotenv import load_dotenv

load_dotenv()

def generate_audio_elevenlabs(script_text, output_file):
    """
    如果您在 .env 填寫了 ELEVENLABS_API_KEY，就會呼叫好萊塢級語音
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key or api_key == "your_elevenlabs_api_key_here":
        return False
        
    print("\n[Audio] 偵測到 ElevenLabs API Key，正在呼叫語音庫...")
    # 使用 Adam 聲音 (預設)
    url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB" 
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    data = {
        "text": script_text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
    }
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        with open(output_file, 'wb') as f:
            f.write(response.content)
        return True
    else:
        print(f"ElevenLabs 錯誤: {response.text}")
        return False

async def generate_audio_edge(script_text, output_file):
    """
    免費備案：呼叫 Microsoft Azure 提供的超逼真神經網路語音 (無字數限制)
    """
    print("\n[Audio] 偵測無 ElevenLabs 授權，自動切換至「完全免費」的首選微軟 Azure 語音 (Edge TTS)...")
    import edge_tts
    # 選擇一位具新聞專業感、有朝氣的男聲 (節奏微微加快 +5% 更像 Podcast)
    voice = "en-US-ChristopherNeural" 
    communicate = edge_tts.Communicate(script_text, voice, rate="+5%")
    await communicate.save(output_file)
    return True

def build_podcast_audio(script_file="script.txt", output_file="podcast.mp3"):
    if not os.path.exists(script_file):
        print(f"找不到講稿: {script_file}")
        return
        
    try:
        with open(script_file, "r", encoding="utf-8-sig") as f:
            script_text = f.read()
    except UnicodeDecodeError:
        # 若使用者在 Windows 上用一般文字編輯器存檔，且改變了編碼 (如 Big5/ANSI)
        with open(script_file, "r", encoding="mbcs") as f:
            script_text = f.read()

    # 清理講稿，避免 AI 念出舞台指示與 Markdown 符號
    import re
    script_text = re.sub(r'\[.*?\]', '', script_text)   # 移除 [Intro Music] 等方括號指示
    script_text = re.sub(r'\(.*?\)', '', script_text)   # 移除 (Upbeat music fades in) 等圓括號指示
    script_text = script_text.replace('*', '')           # 移除粗體星號
    script_text = script_text.replace('#', '')           # 移除標題符號
    script_text = script_text.replace('_', '')           # 移除底線 (斜體)
    script_text = script_text.replace('---', ' ')        # 移除分隔線
    script_text = re.sub(r'\n{3,}', '\n\n', script_text) # 清除多餘空行

    # 1. 嘗試用 ElevenLabs
    success = generate_audio_elevenlabs(script_text, output_file)
    
    # 2. 十一實驗室失敗或無金鑰，就用霸王級免費語音 (Edge TTS)
    if not success:
        try:
            asyncio.run(generate_audio_edge(script_text, output_file))
            success = True
        except ImportError:
            print("\n❌ 尚未安裝 edge-tts 套件，請執行：")
            print("pip install edge-tts")
            return
            
    if success:
        print(f"\n🎧 廣播生成大功告成！檔案已儲存為：{output_file}")
        print("快去專案資料夾點開 mp3，戴上耳機試聽今天的台灣每日重點吧！")

if __name__ == "__main__":
    build_podcast_audio()
