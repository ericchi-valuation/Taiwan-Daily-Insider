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
        res_data = res.json()
        
        if "error" in res_data:
            print(f"❌ 建立 Threads 容器失敗: {res_data['error']['message']}")
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
        pub_data = pub_res.json()
        
        if "id" in pub_data:
            print(f"✅ Threads 貼文發布成功！貼文 ID: {pub_data['id']}")
            return True
        else:
            print(f"❌ Threads 發布失敗: {pub_data}")
            return False

    except Exception as e:
        print(f"❌ 發送 Threads 請求時發生錯誤: {e}")
        return False

# 測試用
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    post_to_threads("這是一篇由 Python 自動透過官方 API 發出的 Threads 測試貼文！✨")
