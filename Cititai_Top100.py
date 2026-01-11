import os
import requests
import sqlite3
import datetime
import re
import time
from collections import Counter
from deep_translator import GoogleTranslator
# ↓ これが足りなかったためにエラーが出ていました
from supabase import create_client, Client 

# --- 設定 ---
# GitHub Secretsから値を取得
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# URLが空でないかチェック
if not url or not key:
    raise ValueError("SupabaseのURLまたはKeyが設定されていません。GitHub Secretsを確認してください。")

# ここでエラーが出ていた箇所の修正が反映されます
supabase: Client = create_client(url, key)

# ... 以下、def fetch_civitai_top_prompts などの続き ...
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

