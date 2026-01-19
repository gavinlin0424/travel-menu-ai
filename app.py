import streamlit as st
import json
import pandas as pd
from PIL import Image
import google.generativeai as genai
import time

# --- 頁面設定 ---
st.set_page_config(page_title="家族旅遊點餐機", page_icon="🍱", layout="centered")

# 手機主畫面圖示設定 (可選)
icon_url = "https://em-content.zobj.net/source/apple/391/sushi_1f363.png"
st.markdown(
    f"""
    <head>
        <link rel="apple-touch-icon" sizes="180x180" href="{icon_url}">
        <link rel="icon" type="image/png" sizes="32x32" href="{icon_url}">
    </head>
    """,
    unsafe_allow_html=True
)

st.title("🍱 點餐神器")
st.caption("拍照 -> AI 翻譯 -> 自動統計")

# --- 1. API Key 安全讀取 ---
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("❌ 未偵測到 API Key！請檢查 Streamlit Secrets 設定。")
    st.stop()

# 設定 Google AI
genai.configure(api_key=api_key)

# --- 2. 核心函式：呼叫 AI (包含自動救援機制) ---
def analyze_menu(image_input):
    """
    嘗試使用最新的 1.5 Flash，如果失敗則自動切換回舊版模型
    """
    prompt_text = """
    你是一個專業的點餐助手。請分析這張菜單圖片：
    1. 識別所有菜色名稱和價格。
    2. 將所有非繁體中文的菜名，翻譯成「台灣習慣的繁體中文」。
    3. 嚴格輸出為 JSON 格式清單：[{"item": "菜名", "price": 數字}, ...]
    4. 如果價格是時價或不明，price 填 0。
    5. 不要使用 Markdown，只輸出純文字 JSON string。
    """
    
    # 策略 A: 優先嘗試 Gemini 1.5 Flash (速度快、效果好)
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content([prompt_text, image_input])
        return response.text
        
    except Exception as e:
        # 策略 B: 如果失敗 (例如 404 錯誤)，切換到舊版 Gemini Pro Vision
        # st.warning(f"正在切換至相容模式... (錯誤代碼: {e})") # Debug用，可註解掉
        time.sleep(1) # 稍等一下
        try:
            model_old = genai.GenerativeModel("gemini-pro-vision")
            # 舊版不支援 JSON mode，所以 Prompt 要強調
            response = model_old.generate_content([prompt_text, image_input])
            return response.text
        except Exception as e2:
            return f"Error: {e2}"

# --- 3. 介面邏輯 ---
uploaded_file = st.file_uploader("📸 請拍下菜單並上傳", type=["jpg", "png", "jpeg", "webp"])

# 初始化 Session State
if 'menu_data' not in st.session_state:
    st.session_state['menu_data'] = None

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="原始菜單", use_container_width=True)
    
    if st.button("✨ 啟動 AI 解析"):
        with st.spinner("AI 正在看菜單... (若第一次執行可能需要幾秒)"):
            result_json_str = analyze_menu(image)
            
            try:
                # 清理回傳的字串，確保是乾淨的 JSON
                clean_json = result_json_str.replace("```json", "").replace("```", "").strip()
                menu_data = json.loads(clean_json)
                st.session_state['menu_data'] = menu_data
                st.success("解析成功！請在下方點餐")
            except:
                st.error("AI 解析失敗，請再試一次或重拍照片。")
                st.expander("查看錯誤詳情").write(result_json_str)

# --- 4. 點餐表單 ---
if st.session_state['menu_data']:
    st.divider()
    st.subheader("📝 點餐區")
    
    menu_items = st.session_state['menu_data']
    order_dict = {}

    with st.form("ordering_form"):
        for idx, dish in enumerate(menu_items):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{dish.get('item', '未命名')}**")
                st.caption(f"${dish.get('price', 0)}")
            with col2:
                order_dict[idx] = st.number_input(
                    "數量", min_value=0, step=1, key=f"qty_{idx}", label_visibility="collapsed"
                )
        
        submitted = st.form_submit_button("💰 結帳統計")

    if submitted:
        total = 0
        details = []
        for idx, dish in enumerate(menu_items):
            qty = order_dict[idx]
            if qty > 0:
                price = dish.get('price', 0)
                subtotal = qty * price
                total += subtotal
                details.append({
                    "品項": dish.get('item'),
                    "單價": price,
                    "數量": qty,
                    "小計": subtotal
                })
        
        if details:
            st.markdown("### 🧾 結帳清單")
            st.table(pd.DataFrame(details))
            st.metric(label="總金額", value=f"${total}")
        else:
            st.warning("還沒點任何東西喔！")