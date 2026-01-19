import streamlit as st
import base64
import json
import pandas as pd
from openai import OpenAI

# --- 頁面設定 ---
st.set_page_config(page_title="點餐神器", page_icon="🍱", layout="centered")

# ... 上面的 import 和 set_page_config ...

# --- 設定手機主畫面圖示 (Mobile App Icon) ---
# 請將下方的 URL 換成你放在 GitHub 上的圖片 Raw URL
# 或是隨便找一個網路上的圖示網址測試
icon_url = "https://github.com/gavinlin0424/travel-menu-ai/blob/08b2da88213c88d9a12ac56627d15d691da5a1ec/app_icon.png"

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


# --- 標題與說明 ---
st.title("🍱 點餐神器")
st.markdown("""
1. 上傳菜單照片（支援日文、英文、韓文等）。
2. AI 會自動翻譯並轉成電子選單。
3. 統計大家的點餐，方便結帳！
""")

# --- 1. API Key 管理 (支援 Streamlit Secrets) ---
# 優先從 Streamlit Cloud 的 Secrets 讀取，如果沒有則讓使用者手動輸入
api_key = st.secrets.get("OPENAI_API_KEY")

if not api_key:
    api_key = st.text_input("請輸入 OpenAI API Key", type="password")

# --- 函式：圖片轉 Base64 ---
def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

# --- 2. 主邏輯 ---
if api_key:
    client = OpenAI(api_key=api_key)
    
    # 上傳圖片
    uploaded_file = st.file_uploader("📸 請拍下菜單並上傳", type=["jpg", "png", "jpeg"])

    # 狀態管理：確保 AI 解析後的菜單不會因為點擊按鈕而消失
    if 'menu_data' not in st.session_state:
        st.session_state['menu_data'] = None

    if uploaded_file:
        # 顯示圖片預覽
        st.image(uploaded_file, caption="原始菜單", use_container_width=True)
        
        # 按鈕觸發 AI 解析
        if st.button("✨ 啟動 AI 解析與翻譯"):
            with st.spinner("AI 正在讀取菜單並翻譯中...請稍等..."):
                try:
                    base64_image = encode_image(uploaded_file)

                    # --- 關鍵 Prompt：視覺辨識 + JSON 格式化 + 翻譯 ---
                    response = client.chat.completions.create(
                        model="gpt-4o",  # 建議使用 gpt-4o 效果最好
                        messages=[
                            {
                                "role": "system",
                                "content": """
                                你是一個專業的菜單解析助手。
                                1. 識別圖片中的菜色名稱和價格。
                                2. 將所有非繁體中文的菜名，翻譯成「台灣習慣的繁體中文」。
                                3. 嚴格輸出為 JSON 格式清單：[{"item": "原本菜名 (中文翻譯)", "price": 數字}...]。
                                4. 如果沒有價格，價格填 0。
                                5. 不要輸出 Markdown (```json)，只輸出純文字 JSON。
                                """
                            },
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "請解析這張菜單。"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                                ]
                            }
                        ],
                        max_tokens=1500
                    )
                    
                    # 處理回傳資料
                    result_text = response.choices[0].message.content
                    # 移除可能的格式符號
                    result_text = result_text.replace("```json", "").replace("```", "").strip()
                    
                    st.session_state['menu_data'] = json.loads(result_text)
                    st.success("解析成功！請在下方點餐。")
                    
                except Exception as e:
                    st.error(f"發生錯誤：{e}")
                    st.write("原始回傳內容：", result_text if 'result_text' in locals() else "無資料")

    # --- 3. 顯示電子表單與統計 ---
    if st.session_state['menu_data']:
        st.divider()
        st.subheader("📝 點餐區")
        
        menu_items = st.session_state['menu_data']
        order_dict = {}

        # 使用 Form 表單，讓使用者一次點完再送出
        with st.form("ordering_form"):
            for idx, dish in enumerate(menu_items):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{dish['item']}**")
                    st.caption(f"${dish['price']}")
                with col2:
                    # 使用唯一 key 避免衝突
                    order_dict[f"{idx}_{dish['item']}"] = st.number_input(
                        "數量", min_value=0, step=1, key=f"qty_{idx}", label_visibility="collapsed"
                    )
            
            submitted = st.form_submit_button("💰 計算總金額")

        # 顯示統計結果
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
                df = pd.DataFrame(details)
                st.table(df)
                st.metric(label="總金額", value=f"${total}")
            else:
                st.warning("您還沒有選擇任何餐點喔！")

else:
    st.info("請先設定 OpenAI API Key 才能開始使用。")