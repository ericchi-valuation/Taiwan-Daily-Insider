import os
import sys

def mix_podcast_audio(voice_file, bgm_file, output_file):
    if not os.path.exists(bgm_file):
        print(f"\n🎧 [提示] 尚未偵測到 {bgm_file}，略過背景配樂混音。")
        print("若是想加入配樂，請將下載好的 mp3 重新命名為 bgm.mp3 放在專案目錄。")
        return False
        
    print(f"\n[混音中心] 發現背景配樂檔，正在將 人聲 與 配樂 結合...")
    print("這可能需要 10~20 秒的高效運算...")
    
    try:
        from pydub import AudioSegment
    except ImportError as e:
        print(f"❌ 載入 pydub 套件失敗：{e}")
        if "audioop" in str(e):
            print("💡 在 Python 3.13 中，系統移除了底層混音庫，請執行：pip install audioop-lts")
        else:
            print("請執行：pip install pydub")
        return False
        
    try:
        voice = AudioSegment.from_file(voice_file)
        bgm = AudioSegment.from_file(bgm_file)
    except FileNotFoundError:
        print("❌ 系統找不到 FFmpeg！這在 Windows 上很常見。")
        print("💡 請打開 PowerShell 執行這行指令來安裝 FFmpeg：")
        print("   winget install ffmpeg")
        print("安裝完畢後，請重新啟動終端機再試一次。")
        return False
    except Exception as e:
        print(f"❌ 讀取音檔失敗：{e}")
        return False
    
    # 算好需要的配樂總長度 = 5秒前奏 + 人聲長度 + 5秒尾奏
    target_len = len(voice) + 10000 
    
    # 如果配樂不夠長，就把它重複播放 (Loop) 到足夠長
    while len(bgm) < target_len:
        bgm += bgm
    bgm = bgm[:target_len] # 裁切成剛好
    
    # 前 5 秒正常音量 (0 dB)，淡出以自然銜接入聲
    intro = bgm[:5000].fade_out(2000)
    
    # 結尾 5 秒正常音量，先淡入再淡出
    outro_start = 5000 + len(voice)
    outro = bgm[outro_start : outro_start + 5000]
    outro = outro.fade_in(2000).fade_out(3000)
    
    # 中間的人聲：不加入背景音樂
    middle_mixed = voice
    
    # 拼湊起來：Intro + Middle + Outro
    final_audio = intro + middle_mixed + outro
    
    # 匯出最後的 MP3！
    try:
        final_audio.export(output_file, format="mp3", bitrate="192k")
        print(f"✅ 後製混音大功告成！加上配樂的 Podcast 已儲存為：{output_file}")
        
        # 把系統原本的純人聲檔稍微改名，當成備份
        os.rename(voice_file, voice_file.replace(".mp3", "_raw_voice_backup.mp3"))
        print("(純人聲檔案已自動備份)")
        return True
    except Exception as e:
        print(f"❌ 匯出過程中發生錯誤：{e}")
        return False
