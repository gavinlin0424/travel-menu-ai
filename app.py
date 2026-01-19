import streamlit as st
import json
import pandas as pd
from PIL import Image
import google.generativeai as genai

# --- 頁面設定 ---
st.set_page_config(page_title="旅遊點餐機", page_icon="🍱", layout="centered")
# ... 上面的 import 和 set_page_config ...

# --- 設定手機主畫面圖示 (Mobile App Icon) ---
# 請將下方的 URL 換成你放在 GitHub 上的圖片 Raw URL
# 或是隨便找一個網路上的圖示網址測試
icon_url = "https://github.com/gavinlin0424/travel-menu-ai/blob/a0eb070625c2249f21bdcc11b3bee24eb68183ed/app_icon.png"

# 這段 HTML 會告訴 Apple 和 Android 裝置使用指定的圖示
st.markdown(
    f"""
    <head>
        <link rel="apple-touch-icon" sizes="180x180" href="{icon_url}">
        <link rel="icon" type="image/png" sizes="32x32" href="{icon_url}">
        <link rel="icon" type="image/png" sizes="16x16" href="{icon_url}">
        <link rel="manifest" href="/site.webmanifest">
    </head>
    """,
    unsafe_allow_html=True
)

# 為了確保 iPhone 能夠正確讀取，有時候需要一個隱藏的圖片元素來預加載
st.markdown(
    f'<img src="{icon_url}" style="display:none;">', 
    unsafe_allow_html=True
)

# ... 下面接原本的主程式 ...
# 設定手機主畫面圖示


st.title("🍱 旅遊點餐APP")
st.caption("Powered by Gemini 2.5 Flash ⚡")

# --- 1. API Key 讀取 ---
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("❌ 未偵測到 API Key！請檢查 Streamlit Secrets 設定。")
    st.stop()

# 設定 Google AI
genai.configure(api_key=api_key)

# --- 2. 核心函式 ---
def analyze_menu(image_input):
    # 這裡使用你清單中確認存在的 gemini-2.5-flash
    # 2.5 版本對 JSON 的支援度非常完美
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash", 
        generation_config={"response_mime_type": "application/json"}
    )
    
    prompt_text = """
    你是一個專業的點餐助手。請分析這張菜單圖片：
    1. 識別所有菜色名稱和價格。
    2. 將所有非繁體中文的菜名，翻譯成「台灣習慣的繁體中文」。
    3. 嚴格輸出為 JSON 格式清單：[{"item": "菜名", "price": 數字}, ...]
    4. 如果價格是時價或不明，price 填 0。
    """
    
    response = model.generate_content([prompt_text, image_input])
    return response.text

# --- 3. 介面邏輯 ---
uploaded_file = st.file_uploader("📸 請拍下菜單並上傳", type=["jpg", "png", "jpeg", "webp"])

# 初始化 Session State
if 'menu_data' not in st.session_state:
    st.session_state['menu_data'] = None

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="原始菜單", use_container_width=True)
    
    if st.button("✨ 啟動 AI 解析 (Gemini 2.5)"):
        with st.spinner("Gemini 2.5 正在極速解析中..."):
            try:
                result_json_str = analyze_menu(image)
                
                # 資料清理
                clean_json = result_json_str.replace("```json", "").replace("```", "").strip()
                menu_data = json.loads(clean_json)
                
                st.session_state['menu_data'] = menu_data
                st.success("解析成功！")
            except Exception as e:
                st.error(f"解析失敗: {e}")
                st.caption("建議：如果是圖片太模糊，請試著重拍一張。")

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
            
            # 產生這份清單的文字版，方便複製到 LINE
            copy_text = "點餐清單：\n"
            for d in details:
                copy_text += f"{d['品項']} x{d['數量']} (${d['小計']})\n"
            copy_text += f"總計: ${total}"
            
            st.text_area("📋 複製以下內容傳到 LINE 群組", value=copy_text, height=150)
            
        else:
            st.warning("還沒點任何東西喔！")