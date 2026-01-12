import os
import requests
import datetime
import re
import time
from collections import Counter
from deep_translator import GoogleTranslator
from supabase import create_client, Client

# --- 1. 設定 ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
translator = GoogleTranslator(source='auto', target='ja')

# --- 2. 1000枚取得用ロジック ---
def fetch_civitai_batch(limit=100, nsfw_param="None", cursor=None):
    url_api = "https://civitai.com/api/v1/images"
    params = {
        "limit": limit,
        "period": "Month",
        "sort": "Most Reactions",
        "nsfw": nsfw_param
    }
    if cursor:
        params["cursor"] = cursor
        
    try:
        response = requests.get(url_api, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get('items', []), data.get('metadata', {}).get('nextCursor')
    except Exception as e:
        print(f"Error fetching: {e}")
        return [], None

def clean_and_tokenize(prompt_text):
    if not prompt_text: return []
    tags = prompt_text.split(',')
    clean_tags = []
    for tag in tags:
        cleaned = re.sub(r'[\(\)\[\]\{\}\:\d\.]', '', tag).strip().lower()
        if len(cleaned) > 2 and len(cleaned) < 40:
            clean_tags.append(cleaned)
    return clean_tags

def translate_text_safe(text):
    try:
        time.sleep(0.5) 
        return translator.translate(text)
    except:
        return text

# --- 3. DB保存ロジック（上位100件対応） ---
def save_ranking_to_supabase(counter, category, rating, current_time):
    # 上位100件を処理
    top_100 = counter.most_common(100)
    print(f"  Saving top {len(top_100)} words for {category}...")
    
    for token_en, count in top_100:
        # マスタ確認
        res = supabase.table("m_prompts").select("prompt_id").eq("token_en", token_en).execute()
        
        if not res.data:
            token_jp = translate_text_safe(token_en)
            res_ins = supabase.table("m_prompts").insert({
                "token_en": token_en, 
                "token_jp": token_jp,
                "status": "unconfirmed",
                "genre": "未分類"
            }).execute()
            prompt_id = res_ins.data[0]["prompt_id"]
        else:
            prompt_id = res.data[0]["prompt_id"]

        # 統計登録
        supabase.table("t_prompt_stats").insert({
            "prompt_id": prompt_id,
            "category": category,
            "rating": rating,
            "count": count,
            "collected_at": current_time,
            "source": "civitai_top1000"
        }).execute()

# --- 4. メイン実行 ---
def main():
    print("--- Start Top 1000 Script ---")
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # SFWとNSFWの両パターン実行
    patterns = [("None", "SFW"), ("X", "NSFW")]

    for nsfw_param, rating_label in patterns:
        all_images = []
        next_cursor = None
        
        # 100枚 × 10回 ＝ 1000枚取得
        print(f"\n[{rating_label}] Fetching 1000 images...")
        for i in range(10):
            print(f"  Batch {i+1}/10...")
            items, next_cursor = fetch_civitai_batch(100, nsfw_param, next_cursor)
            all_images.extend(items)
            if not next_cursor: break
            time.sleep(1) # 負荷軽減

        pos_counter = Counter()
        neg_counter = Counter()

        print(f"  Processing {len(all_images)} images data...")
        for img in all_images:
            meta = img.get('meta')
            if meta:
                pos_counter.update(clean_and_tokenize(meta.get('prompt')))
                neg_counter.update(clean_and_tokenize(meta.get('negativePrompt')))

        # DB保存（上位100ワード）
        save_ranking_to_supabase(pos_counter, 'positive', rating_label, current_time)
        save_ranking_to_supabase(neg_counter, 'negative', rating_label, current_time)

    print("\n--- All Processes Completed Successfully ---")

if __name__ == "__main__":
    main()
