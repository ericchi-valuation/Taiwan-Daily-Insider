import os
import time
import requests

def post_to_threads(text_content):
    """
    透過官方 Meta Threads API 發布純文字貼文
    """
    threads_user_id = os.getenv("THREADS_USER_ID")
    access_token = os.getenv("THREADS_ACCESS_TOKEN")

    if not threads_user_id or not access_token:
        print("⚠️ 缺少 Threads 登入資訊 (THREADS_USER_ID 或 THREADS_ACCESS_TOKEN)，跳過發布 Threads。")
        return False

    print("🧵 準備發布貼文至 Threads...")
    
    # 限制字數以符合 Threads 官方上限 (500字元)
    if len(text_content) > 500:
        print("⚠️ 貼文超過 500 字元，將自動截斷並加上 '...'")
        text_content = text_content[:496] + "..."

    # 步驟 1: 建立媒體容器 (Media Container)
    create_container_url = f"https://graph.threads.net/v1.0/{threads_user_id}/threads"
    payload = {
        "media_type": "TEXT",
        "text": text_content,
        "access_token": access_token
    }

    try:
        res = requests.post(create_container_url, data=payload)
        res_data = _safe_parse(res, step="建立容器")
        if res_data is None:
            return False
        
        if "error" in res_data:
            _print_api_error(res_data["error"], res.status_code)
            return False
            
        creation_id = res_data.get("id")
        print(f"  ✔️ 容器建立成功，ID: {creation_id}。準備發布...")
        
        # 官方建議等待一下讓 Server 就緒
        time.sleep(3)

        # 步驟 2: 發布剛建立的容器
        publish_url = f"https://graph.threads.net/v1.0/{threads_user_id}/threads_publish"
        publish_payload = {
            "creation_id": creation_id,
            "access_token": access_token
        }
        
        pub_res = requests.post(publish_url, data=publish_payload)
        pub_data = _safe_parse(pub_res, step="發布貼文")
        if pub_data is None:
            return False

        if "error" in pub_data:
            _print_api_error(pub_data["error"], pub_res.status_code)
            return False

        if "id" in pub_data:
            print(f"✅ Threads 貼文發布成功！貼文 ID: {pub_data['id']}")
            return True
        else:
            print(f"❌ Threads 發布失敗，API 回應: {pub_data}")
            return False

    except Exception as e:
        print(f"❌ 發送 Threads 請求時發生未預期錯誤: {e}")
        return False


def _safe_parse(response, step="API 呼叫"):
    """
    安全地解析 HTTP 回應為 JSON。
    若回應為空或非 JSON，印出詳細錯誤後回傳 None。
    """
    status = response.status_code
    raw = response.text.strip()

    if not raw:
        print(f"❌ [{step}] API 回傳空白回應 (HTTP {status})。")
        if status in (400, 401):
            print("  💡 最可能原因：THREADS_ACCESS_TOKEN 已過期（Meta 長期 Token 有效期為 60 天）。")
            print("  💡 請至 Meta Developer Console 重新產生 Token，並更新 GitHub Secret：THREADS_ACCESS_TOKEN")
        return None

    try:
        return response.json()
    except Exception:
        print(f"❌ [{step}] API 回傳非 JSON 內容 (HTTP {status}):")
        print(f"   {raw[:300]}")
        if status in (400, 401):
            print("  💡 最可能原因：THREADS_ACCESS_TOKEN 已過期（Meta 長期 Token 有效期為 60 天）。")
            print("  💡 請至 Meta Developer Console 重新產生 Token，並更新 GitHub Secret：THREADS_ACCESS_TOKEN")
        return None


def _print_api_error(error_dict, status_code):
    """印出 Meta Graph API 標準錯誤格式"""
    msg  = error_dict.get("message", "Unknown error")
    code = error_dict.get("code", "?")
    print(f"❌ Threads API 錯誤 (HTTP {status_code}, code {code}): {msg}")
    if status_code in (400, 401) or code in (190, 102):
        print("  💡 最可能原因：THREADS_ACCESS_TOKEN 已過期（Meta 長期 Token 有效期為 60 天）。")
        print("  💡 請至 Meta Developer Console 重新產生 Token，並更新 GitHub Secret：THREADS_ACCESS_TOKEN")


# 測試用
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    post_to_threads("這是一篇由 Python 自動透過官方 API 發出的 Threads 測試貼文！✨")
