import streamlit as st
import json
import pandas as pd
from PIL import Image
import google.generativeai as genai

# --- 頁面設定 ---
st.set_page_config(page_title="點餐系統", page_icon="🍱", layout="centered")

# --- 設定手機主畫面圖示 (可選) ---
# icon_url = "https://github.com/gavinlin0424/travel-menu-ai/blob/08b2da88213c88d9a12ac56627d15d691da5a1ec/app_icon.png"
# st.markdown(...) # 如果你有設定圖示的話保留這段，沒有就跳過

st.title("🍱 點餐系統")
st.caption("Powered by Google Gemini 1.5 Flash")

st.markdown("""
1. 📸 上傳菜單照片
2. 🤖 AI 自動翻譯並整理
3. 🛒 大家一起點餐
""")

# --- 1. API Key 管理 ---
# 這裡我們讀取 secrets 中的 GOOGLE_API_KEY
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    api_key = st.text_input("請輸入 Google AI Studio API Key", type="password")

# --- 2. 主邏輯 ---
if api_key:
    # 設定 Google Generative AI
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"API Key 設定失敗: {e}")

    # 上傳圖片
    uploaded_file = st.file_uploader("請拍下菜單並上傳", type=["jpg", "png", "jpeg", "webp"])

    # 狀態管理
    if 'menu_data' not in st.session_state:
        st.session_state['menu_data'] = None

    if uploaded_file:
        # 顯示圖片 (調整寬度以適應手機)
        image = Image.open(uploaded_file)
        st.image(image, caption="原始菜單", use_container_width=True)
        
        # 按鈕觸發
        if st.button("✨ 啟動 AI 解析與翻譯"):
            with st.spinner("Gemini 正在看菜單..."):
                try:
                    # 設定模型：使用 Gemini 1.5 Flash (速度快、視覺強)
                    # generation_config 設定回應格式為 JSON，這點非常重要！
                    model = genai.GenerativeModel(
                        model_name="gemini-1.5-flash",
                        generation_config={"response_mime_type": "application/json"}
                    )

                    prompt = """
                    你是一個專業的點餐助手。請分析這張菜單圖片：
                    1. 識別所有菜色名稱和價格。
                    2. 將所有非繁體中文的菜名，翻譯成「台灣習慣的繁體中文」。
                    3. 輸出格式必須是以下的 JSON list schema：
                       [{"item": "菜名 (翻譯)", "price": 數字}, ...]
                    4. 如果價格是時價或不明，price 填 0。
                    """

                    # 發送請求 (圖片直接傳給 Gemini，不需要轉 Base64)
                    response = model.generate_content([prompt, image])
                    
                    # Gemini 在 JSON 模式下會直接回傳乾淨的 JSON 字串
                    menu_data = json.loads(response.text)
                    
                    st.session_state['menu_data'] = menu_data
                    st.success("解析成功！")
                    
                except Exception as e:
                    st.error(f"發生錯誤：{e}")
                    # 如果解析 JSON 失敗，印出原始文字方便除錯
                    if 'response' in locals():
                        st.write("原始回傳內容：", response.text)

    # --- 3. 點餐介面 (這部分邏輯不變) ---
    if st.session_state['menu_data']:
        st.divider()
        st.subheader("📝 點餐區")
        
        menu_items = st.session_state['menu_data']
        order_dict = {}

        with st.form("ordering_form"):
            for idx, dish in enumerate(menu_items):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{dish['item']}**")
                    st.caption(f"${dish['price']}")
                with col2:
                    order_dict[f"{idx}_{dish['item']}"] = st.number_input(
                        "數量", min_value=0, step=1, key=f"qty_{idx}", label_visibility="collapsed"
                    )
            
            submitted = st.form_submit_button("💰 計算總金額")

        if submitted:
            total = 0
            details = []
            for idx, dish in enumerate(menu_items):
                qty = order_dict[f"{idx}_{dish['item']}"]
                if qty > 0:
                    subtotal = qty * dish['price']
                    total += subtotal
                    details.append({
                        "品項": dish['item'],
                        "單價": dish['price'],
                        "數量": qty,
                        "小計": subtotal
                    })
            
            if details:
                st.markdown("### 🧾 結帳清單")
                st.table(pd.DataFrame(details))
                st.metric(label="總金額", value=f"${total}")
            else:
                st.warning("還沒點餐喔！")

else:
    st.info("請輸入 Google API Key 才能使用。")