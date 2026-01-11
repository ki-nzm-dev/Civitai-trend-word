import os
import requests
import datetime
import re
import time
from collections import Counter
from deep_translator import GoogleTranslator
from supabase import create_client, Client

# --- 1. 設定 (GitHub Secretsから取得) ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("SupabaseのURLまたはKeyが設定されていません。GitHub Secretsを確認してください。")

supabase: Client = create_client(url, key)
translator = GoogleTranslator(source='auto', target='ja')

# --- 2. データ取得・整形ロジック ---
def fetch_civitai_top_prompts(limit=100, nsfw_param="None"):
    url_api = "https://civitai.com/api/v1/images"
    params = {
        "limit": limit,
        "period": "Month",
        "sort": "Most Reactions",
        "nsfw": nsfw_param
    }
    try:
        response = requests.get(url_api, params=params)
        response.raise_for_status()
        return response.json().get('items', [])
    except Exception as e:
        print(f"Error fetching (NSFW={nsfw_param}): {e}")
        return []

def is_valid_token(token):
    token = token.lower()
    blacklist = ["http", "https", "www", ".com", "click", "link", "message", "dm me", 
                 "send me", "read the full story", "prompt codes", "emoji", "translation", "lora:", "<lora"]
    if any(ng in token for ng in blacklist): return False
    if len(token) < 2 or len(token) > 40: return False
    return True

def clean_and_tokenize(prompt_text):
    if not prompt_text: return []
    tags = prompt_text.split(',')
    clean_tags = []
    for tag in tags:
        cleaned = re.sub(r'[\(\)\[\]\{\}\:\d\.]', '', tag).strip().lower()
        if is_valid_token(cleaned):
            clean_tags.append(cleaned)
    return clean_tags

def translate_text_safe(text):
    try:
        time.sleep(0.5) 
        return translator.translate(text)
    except:
        return text

# --- 3. DB保存ロジック ---
def save_ranking_to_supabase(counter, category, rating, current_time):
    print(f"  Saving {category} ranking ({rating}) to Supabase...")
    for token_en, count in counter.most_common(30):
        # 1. マスタ確認
        res = supabase.table("m_prompts").select("prompt_id").eq("token_en", token_en).execute()
        
        if not res.data:
            # 2. なければ翻訳して登録
            print(f"    New token: {token_en} -> Translating...")
            token_jp = translate_text_safe(token_en)
            res_ins = supabase.table("m_prompts").insert({"token_en": token_en, "token_jp": token_jp}).execute()
            prompt_id = res_ins.data[0]["prompt_id"]
        else:
            prompt_id = res.data[0]["prompt_id"]

        # 3. トランザクション登録
        supabase.table("t_prompt_stats").insert({
            "prompt_id": prompt_id,
            "category": category,
            "rating": rating,
            "count": count,
            "collected_at": current_time
        }).execute()

# --- 4. メイン実行関数 ---
def main():
    print("--- Start Script ---")
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    fetch_patterns = [
        ("None", "SFW", "Safe Content"), 
        ("X", "NSFW", "NSFW Content")
    ]

    for nsfw_param, rating_label, display_name in fetch_patterns:
        print(f"\n[{display_name}] Fetching data...")
        images = fetch_civitai_top_prompts(100, nsfw_param)
        
        pos_counter = Counter()
        neg_counter = Counter()

        print(f"[{display_name}] Processing {len(images)} images...")
        for img in images:
            meta = img.get('meta')
            if meta:
                pos_counter.update(clean_and_tokenize(meta.get('prompt')))
                neg_counter.update(clean_and_tokenize(meta.get('negativePrompt')))

        # DB保存実行
        save_ranking_to_supabase(pos_counter, 'positive', rating_label, current_time)
        save_ranking_to_supabase(neg_counter, 'negative', rating_label, current_time)

    print("\n--- All Processes Completed Successfully ---")

# --- 5. 実行エントリーポイント (ここが重要！) ---
if __name__ == "__main__":
    main()
