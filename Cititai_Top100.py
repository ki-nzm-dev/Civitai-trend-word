import os
from supabase import create_client, Client

# SupabaseのURLとKey（設定画面から取得）
url: str = "あなたのSUPABASE_URL"
key: str = "あなたのSUPABASE_ANON_KEY"
supabase: Client = create_client(url, key)

def save_ranking_to_supabase(counter, category, rating, current_time):
    for token_en, count in counter.most_common(30):
        # 1. マスタ確認 (SELECT)
        res = supabase.table("m_prompts").select("prompt_id").eq("token_en", token_en).execute()
        
        if not res.data:
            # 2. なければ翻訳して登録 (INSERT)
            token_jp = translate_text_safe(token_en)
            res = supabase.table("m_prompts").insert({"token_en": token_en, "token_jp": token_jp}).execute()
            prompt_id = res.data[0]["prompt_id"]
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