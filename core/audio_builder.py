import os
import re
import requests
import asyncio
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# ===========================================================================
# Voice Design Prompt for "Eric" — The Taiwan Daily Insider host
# Used by VoxCPM2 only (natural-language voice design in parentheses)
# ===========================================================================
ERIC_VOICE_DESIGN = (
    "(A professional English-speaking male news anchor in his early 40s. "
    "Warm, confident, and authoritative NPR-style voice with clear diction. "
    "Energetic yet measured pace, like a seasoned radio host.)"
)

# Kokoro voice for "Eric" — American male news anchor style
# Available male voices: am_adam, am_echo, am_liam, am_michael, am_onyx
# Available British male: bm_george, bm_lewis (more BBC/news-anchor feel)
KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "am_adam")


# ===========================================================================
# Helper: split long scripts into sentence-boundary chunks (for VoxCPM2)
# ===========================================================================
def _split_into_chunks(text: str, max_chars: int = 500) -> list:
    """
    Split text into chunks at sentence boundaries so VoxCPM2 produces
    natural-sounding audio without cutoffs.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            sub_parts = sentence.split(', ')
            for part in sub_parts:
                if len(current) + len(part) + 2 <= max_chars:
                    current = (current + " " + part).strip() if current else part
                else:
                    if current:
                        chunks.append(current)
                    current = part
        elif len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip() if current else sentence
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


# ===========================================================================
# TTS Option 1: ElevenLabs (Premium paid API)
# ===========================================================================
def generate_audio_elevenlabs(script_text, output_file):
    """
    如果您在 .env 填寫了 ELEVENLABS_API_KEY，就會呼叫好萊塢級語音
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key or api_key == "your_elevenlabs_api_key_here":
        return False

    print("\n[Audio] ElevenLabs API Key detected — calling premium voice synthesis...")
    url = "https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    data = {
        "text": script_text,
        "model_id": "eleven_multilingual_v2",
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


# ===========================================================================
# TTS Option 2: VoxCPM2 (Open-source — local GPU only)
# Enable via: USE_VOXCPM=true in .env
# NOT suitable for GitHub Actions (requires GPU + large model download)
# ===========================================================================
def generate_audio_voxcpm(script_text, output_file):
    """
    Use VoxCPM2 to generate high-quality podcast audio locally.

    Requirements:
        pip install voxcpm soundfile torch numpy

    Enable by setting USE_VOXCPM=true in your .env file.
    Strongly recommended to have a CUDA-capable GPU for reasonable speed.
    On CPU: expect 10-30 minutes for a 10-minute podcast script.

    This option is SKIPPED on GitHub Actions (USE_VOXCPM is not set there).
    """
    use_voxcpm = os.environ.get("USE_VOXCPM", "").strip().lower() in ("1", "true", "yes")
    if not use_voxcpm:
        return False

    try:
        from voxcpm import VoxCPM
        import soundfile as sf
        import torch
    except ImportError as e:
        print(f"\n[Audio] ⚠️  VoxCPM2 not installed ({e}).")
        print("       Run: pip install voxcpm soundfile torch")
        return False

    print("\n[Audio] 🎤 VoxCPM2 enabled — generating premium open-source TTS...")

    try:
        if torch.cuda.is_available():
            device = "cuda"
            print(f"  ✔️  GPU detected: {torch.cuda.get_device_name(0)}")
        else:
            device = "cpu"
            print("  ⚠️  No GPU detected. Running VoxCPM2 on CPU (may be slow).")

        print("  Loading VoxCPM2 model (first run auto-downloads from Hugging Face)...")
        model = VoxCPM.from_pretrained("openbmb/VoxCPM2", device=device)
        sample_rate = model.tts_model.sample_rate

        chunks = _split_into_chunks(script_text, max_chars=500)
        print(f"  Script split into {len(chunks)} chunks for chunked inference.")

        all_audio = []
        for i, chunk in enumerate(chunks, 1):
            text_with_voice = f"{ERIC_VOICE_DESIGN} {chunk}" if i == 1 else chunk
            print(f"  [VoxCPM2] Chunk {i}/{len(chunks)}: {chunk[:60]}...")
            wav = model.generate(
                text=text_with_voice,
                cfg_value=2.0,
                inference_timesteps=10
            )
            all_audio.append(wav)

        combined_audio = np.concatenate(all_audio)
        print(f"  ✔️  Total audio: {len(combined_audio) / sample_rate:.1f}s")

        wav_file = output_file.replace(".mp3", "_voxcpm_raw.wav")
        import soundfile as sf
        sf.write(wav_file, combined_audio, sample_rate)

        from pydub import AudioSegment
        sound = AudioSegment.from_wav(wav_file)
        sound.export(output_file, format="mp3", bitrate="192k")

        if os.path.exists(wav_file):
            os.remove(wav_file)

        print(f"  ✔️  VoxCPM2 audio ready: {output_file}")
        return True

    except Exception as e:
        print(f"\n  ❌ VoxCPM2 generation failed: {e}")
        return False


# ===========================================================================
# TTS Option 3: Kokoro TTS (Open-source — CPU-friendly, GitHub Actions ready)
# ✨ This is the recommended FREE option for automated cloud pipelines.
#
# Quality: Rivals paid services, ranks #1 on open-source TTS leaderboards.
# Speed:   ~5x real-time on CPU → 10-min podcast generated in ~2 minutes.
# Install: pip install kokoro>=0.9.4
# System:  Requires espeak-ng (auto-installed in GitHub Actions via workflow)
#
# Voice selection via KOKORO_VOICE env var (default: am_adam)
#   American male:  am_adam, am_echo, am_liam, am_michael, am_onyx
#   British male:   bm_george, bm_lewis (more BBC news-anchor feel)
#   American female:af_heart, af_bella, af_nicole (if you prefer female host)
# ===========================================================================
def generate_audio_kokoro(script_text, output_file):
    """
    Generate podcast audio using Kokoro TTS — the best free option for
    automated pipelines including GitHub Actions (no GPU required).
    """
    try:
        from kokoro import KPipeline
        import soundfile as sf
    except ImportError:
        # Silently skip if not installed — Edge TTS will handle it
        return False

    print(f"\n[Audio] 🎙️  Kokoro TTS — generating high-quality CPU audio (voice: {KOKORO_VOICE})...")

    try:
        # 'a' = American English, 'b' = British English
        lang_code = 'b' if KOKORO_VOICE.startswith('b') else 'a'
        pipeline = KPipeline(lang_code=lang_code)

        all_audio = []
        total_chunks = 0
        print("  Processing script (Kokoro handles long text natively)...")

        for graphemes, phonemes, audio in pipeline(
            script_text,
            voice=KOKORO_VOICE,
            speed=1.05  # Slightly faster — podcast-style pace
        ):
            all_audio.append(audio)
            total_chunks += 1

        if not all_audio:
            print("  ❌ Kokoro generated no audio chunks.")
            return False

        combined = np.concatenate(all_audio)
        duration = len(combined) / 24000
        print(f"  ✔️  {total_chunks} chunks generated. Total: {duration:.1f}s ({duration/60:.1f} min)")

        # Save WAV then convert to MP3
        wav_file = output_file.replace(".mp3", "_kokoro_raw.wav")
        sf.write(wav_file, combined, 24000)  # Kokoro sample rate is 24kHz

        from pydub import AudioSegment
        sound = AudioSegment.from_wav(wav_file)
        sound.export(output_file, format="mp3", bitrate="192k")

        if os.path.exists(wav_file):
            os.remove(wav_file)

        print(f"  ✔️  Kokoro MP3 ready: {output_file}")
        return True

    except Exception as e:
        print(f"  ❌ Kokoro TTS failed: {e}")
        print("     Falling back to Edge TTS...")
        return False


# ===========================================================================
# TTS Option 4: Edge TTS (Ultimate fallback — free, Microsoft Azure Neural)
# No GPU, no large model download, works anywhere.
# ===========================================================================
async def generate_audio_edge(script_text, output_file):
    """
    免費備案：呼叫 Microsoft Azure 提供的超逼真神經網路語音 (無字數限制)
    Works on any machine, including GitHub Actions runners (no GPU required).
    """
    print("\n[Audio] Falling back to free Microsoft Azure Edge TTS...")
    import edge_tts
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(script_text, voice, rate="+5%")
    await communicate.save(output_file)
    return True


# ===========================================================================
# Main pipeline entry point
# Priority: ElevenLabs → VoxCPM2 → Kokoro TTS → Edge TTS
# ===========================================================================
def build_podcast_audio(script_file="script.txt", output_file="podcast.mp3"):
    if not os.path.exists(script_file):
        print(f"找不到講稿: {script_file}")
        return

    try:
        with open(script_file, "r", encoding="utf-8-sig") as f:
            script_text = f.read()
    except UnicodeDecodeError:
        with open(script_file, "r", encoding="mbcs") as f:
            script_text = f.read()

    # 清理講稿，避免 AI 念出舞台指示與 Markdown 符號
    script_text = re.sub(r'\[.*?\]', '', script_text)
    script_text = re.sub(r'\(.*?\)', '', script_text)
    script_text = script_text.replace('*', '')
    script_text = script_text.replace('#', '')
    script_text = script_text.replace('_', '')
    script_text = script_text.replace('---', ' ')
    script_text = re.sub(r'\n{3,}', '\n\n', script_text)

    print("\n[Audio] TTS Priority: ElevenLabs → VoxCPM2 (local GPU) → Kokoro → Edge TTS")

    # ── Priority 1: ElevenLabs (premium paid TTS) ─────────────────────────
    success = generate_audio_elevenlabs(script_text, output_file)

    # ── Priority 2: VoxCPM2 (local GPU, opt-in via USE_VOXCPM=true) ───────
    if not success:
        success = generate_audio_voxcpm(script_text, output_file)

    # ── Priority 3: Kokoro TTS (free, CPU-friendly, GitHub Actions ready) ─
    if not success:
        success = generate_audio_kokoro(script_text, output_file)

    # ── Priority 4: Edge TTS (ultimate fallback — always works) ───────────
    if not success:
        try:
            asyncio.run(generate_audio_edge(script_text, output_file))
            success = True
        except Exception as e:
            print(f"\n❌ Error generating Edge TTS audio: {e}")
            print("Please ensure edge-tts is installed: pip install edge-tts")
            return

    if success:
        print(f"\n🎧 Audio generated! Saved as: {output_file}")
        print("Put on your headphones and enjoy today's Taiwan Daily Insider!")


if __name__ == "__main__":
    build_podcast_audio()
