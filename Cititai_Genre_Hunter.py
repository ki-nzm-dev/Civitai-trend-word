import os
import requests
import datetime
import re
import time
from collections import Counter
from supabase import create_client, Client

# --- 設定 ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("SupabaseのURLまたはKeyが設定されていません。")

supabase: Client = create_client(url, key)

GENRE_MAP = {
    "髪型・髪色": ["hair", "hairstyle", "hair color", "twintails", "ponytail"],
    "服装": ["clothing", "outfit", "dress", "uniform", "suit"],
    "顔・表情": ["facial expression", "eyes", "smile", "blush", "open mouth"],
    "身体・体形": ["body", "physique", "skin", "thighs"],
    "動作・ポーズ": ["pose", "action", "sitting", "standing", "lying"],
    "場所・背景": ["background", "scenery", "indoors", "outdoors", "sky"],
    "視点・構図": ["perspective", "view", "angle", "from above", "from below"],
    "職業・属性": ["occupation", "job", "role", "student", "knight"]
}

def fetch_by_tag(tag_name, limit=100):
    url_api = "https://civitai.com/api/v1/images"
    # パラメータ設定
    params = {"limit": limit, "sort": "Most Reactions", "period": "AllTime", "tag": tag_name, "nsfw": "None"}
    try:
        res = requests.get(url_api, params=params, timeout=10)
        res.raise_for_status()
        items = res.json().get('items', [])
        print(f"    - Found {len(items)} images for tag: {tag_name}")
        return items
    except Exception as e:
        print(f"    - Error fetching {tag_name}: {e}")
        return []

def clean_token(tag_text):
    if not tag_text: return None
    # 記号を除去し、小文字化
    cleaned = re.sub(r'[\(\)\[\]\{\}\:\d\.]', '', tag_text).strip().lower()
    # 2文字以下や、除外したい単語があればここで弾く
    if len(cleaned) < 2: return None
    if cleaned in ["lora", "masterpiece", "best quality"]: return None # ノイズ除去
    return cleaned

def save_to_supabase(token_en, genre_name):
    try:
        # すでにマスタにあるか確認
        res = supabase.table("m_prompts").select("prompt_id, genre").eq("token_en", token_en).execute()
        
        if not res.data:
            # 新規登録
            supabase.table("m_prompts").insert({
                "token_en": token_en,
                "token_jp": token_en, # 翻訳は後回し
                "genre": genre_name,
                "status": "unconfirmed"
            }).execute()
            return True
        elif res.data[0].get('genre') == '未分類':
            # 既存だが未分類なら、ジャンルを更新
            supabase.table("m_prompts").update({"genre": genre_name}).eq("token_en", token_en).execute()
            return False
        return False
    except Exception as e:
        print(f"    ! DB Error ({token_en}): {e}")
        return False

def main():
    print("--- Genre Hunting Start ---")
    new_count = 0
    
    for genre_name, tags in GENRE_MAP.items():
        print(f"\n[Genre: {genre_name}]")
        word_counter = Counter()

        for tag in tags:
            items = fetch_by_tag(tag)
            for item in items:
                # --- ここを修正しました ---
                meta = item.get('meta')
                
                # meta情報がない、またはプロンプトがない画像はスキップ
                if not meta or not meta.get('prompt'):
                    continue

                prompt = meta.get('prompt')
                tokens = [clean_token(t) for t in prompt.split(',') if clean_token(t)]
                word_counter.update(tokens)
            
            time.sleep(1) # API負荷軽減

        # 頻出上位50件を処理
        print(f"  > Processing top 50 tokens for {genre_name}...")
        for token, count in word_counter.most_common(50):
            if save_to_supabase(token, genre_name):
                new_count += 1
                print(f"    + New: {token}")

    print(f"\n--- Process Completed. New tokens added: {new_count} ---")

if __name__ == "__main__":
    main()
