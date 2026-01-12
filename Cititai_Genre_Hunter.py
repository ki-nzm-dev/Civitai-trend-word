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
supabase: Client = create_client(url, key)

# あなたが挙げた「集めたいジャンル」と、それに対応するCivitaiの検索タグ
GENRE_MAP = {
    "髪型・髪色": ["hair", "hairstyle"],
    "服装": ["clothing", "fashion", "outfit"],
    "顔・表情": ["face", "expression", "eyes"],
    "身体・体形": ["body", "physique"],
    "動作・ポーズ": ["pose", "action"],
    "場所・背景": ["background", "scenery", "environment"],
    "視点・構図": ["composition", "camera angle", "perspective"],
    "職業・属性": ["character", "occupation"]
}

def fetch_by_tag(tag, limit=100):
    url_api = "https://civitai.com/api/v1/images"
    params = {"limit": limit, "sort": "Most Reactions", "period": "AllTime", "tags": tag, "nsfw": "None"}
    try:
        res = requests.get(url_api, params=params)
        return res.json().get('items', [])
    except:
        return []

def clean_token(tag):
    cleaned = re.sub(r'[\(\)\[\]\{\}\:\d\.]', '', tag).strip().lower()
    return cleaned if len(cleaned) > 2 else None

def save_to_supabase(token_en, genre_name):
    # すでにマスタにあるか確認
    res = supabase.table("m_prompts").select("prompt_id").eq("token_en", token_en).execute()
    if not res.data:
        # 新規登録（翻訳は後でGeminiに任せるので、一旦英語をそのまま入れるか空にする）
        supabase.table("m_prompts").insert({
            "token_en": token_en,
            "token_jp": token_en, # 一旦英語を入れておく
            "genre": genre_name,
            "status": "unconfirmed"
        }).execute()
        print(f"  [New] {token_en} ({genre_name})")

def main():
    print("--- Genre Hunting Start ---")
    for genre_name, tags in GENRE_MAP.items():
        print(f"\nTargeting Genre: {genre_name}")
        word_counter = Counter()

        for tag in tags:
            print(f"  Searching tag: {tag}...")
            items = fetch_by_tag(tag)
            for item in items:
                meta = item.get('meta', {})
                prompt = meta.get('prompt', "")
                if prompt:
                    tokens = [clean_token(t) for t in prompt.split(',') if clean_token(t)]
                    word_counter.update(tokens)
            time.sleep(1) # API負荷軽減

        # 各ジャンルの頻出上位50件をマスタ候補として保存
        for token, count in word_counter.most_common(50):
            save_to_supabase(token, genre_name)

if __name__ == "__main__":
    main()
