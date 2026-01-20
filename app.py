import streamlit as st
import pandas as pd
import json
import time
from PIL import Image
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# --- 📱 手機版面設定 CSS ---
st.set_page_config(page_title="點餐系統", page_icon="🍱", layout="centered")
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

# 注入 CSS：加大字體、優化按鈕、卡片樣式
st.markdown("""
    <style>
    /* 全域字體優化 */
    html, body, [class*="css"] {
        font-family: 'Heiti TC', 'Microsoft JhengHei', sans-serif;
    }
    /* Tab 標籤加大 */
    button[data-baseweb="tab"] {
        font-size: 16px !important;
        padding: 10px !important;
        flex: 1; /* 讓 Tab 平均分配寬度 */
    }
    /* 數字輸入框 */
    input[type="number"] {
        font-size: 18px !important; 
        text-align: center; 
    }
    /* 按鈕樣式 */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    /* 標題與間距 */
    h1 { font-size: 24px !important; }
    h2 { font-size: 20px !important; }
    h3 { font-size: 18px !important; }
    
    /* 卡片容器 (讓菜單看起來像一張張卡片) */
    div.dish-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #e0e0e0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 連線設定 ---
# 1. AI 設定
api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key:
    st.error("❌ 缺少 GOOGLE_API_KEY")
    st.stop()
genai.configure(api_key=api_key)

# 2. Google Sheets 設定 (這裡會自動抓取 secrets 裡的 [connections.gsheets])
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("連線設定錯誤，請檢查 Secrets 格式")
    st.stop()

# --- 資料庫操作函式 ---
def fetch_data():
    # 這裡加上 retry 機制，避免網路波動
    try:
        menu_df = conn.read(worksheet="Menu", ttl=0)
        orders_df = conn.read(worksheet="Orders", ttl=0)
    except:
        # 如果讀不到，回傳空的 DataFrame
        menu_df = pd.DataFrame(columns=["item", "price"])
        orders_df = pd.DataFrame(columns=["name", "item", "qty"])
    return menu_df, orders_df

def save_menu(df):
    conn.update(worksheet="Menu", data=df)

def save_orders(df):
    conn.update(worksheet="Orders", data=df)

# --- 👋 登入畫面 (全螢幕) ---
if "user_name" not in st.session_state or not st.session_state.user_name:
    st.title("🍱 家族點餐")
    st.write("輸入名字即可加入連線：")
    
    name_input = st.text_input("你的名字", placeholder="例如：爸爸、小明...")
    
    if st.button("🚀 進入點餐", type="primary"):
        if name_input.strip():
            st.session_state.user_name = name_input.strip()
            st.rerun()
        else:
            st.toast("請輸入名字喔！")
    st.stop() # 停止執行下方程式碼

# --- 主程式 ---
st.caption(f"👤 當前身份：{st.session_state.user_name}")

# 讀取資料
menu_df, orders_df = fetch_data()

# 確保欄位存在
if menu_df.empty: menu_df = pd.DataFrame(columns=["item", "price"])
if orders_df.empty: orders_df = pd.DataFrame(columns=["name", "item", "qty"])

# 分頁設計
tab1, tab2, tab3 = st.tabs(["🍽️ 點餐", "📊 統計", "➕ 加菜"])

# =======================
# Tab 1: 手機版點餐介面
# =======================
with tab1:
    if menu_df.empty:
        st.info("菜單是空的，請去「➕ 加菜」分頁新增。")
    else:
        # 準備使用者的舊訂單
        my_orders = orders_df[orders_df['name'] == st.session_state.user_name]
        my_order_map = dict(zip(my_orders['item'], my_orders['qty']))
        
        current_input = {}
        
        with st.form("mobile_order_form"):
            st.write("請選擇數量：")
            
            # 使用迴圈生成卡片式介面
            for index, row in menu_df.iterrows():
                dish = row['item']
                price = row['price']
                default_qty = int(my_order_map.get(dish, 0))
                
                # HTML 卡片樣式
                st.markdown(f"""
                <div class="dish-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:18px; font-weight:bold;">{dish}</span>
                        <span style="color:#666;">${price}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 數量輸入 (緊接在卡片下方)
                current_input[dish] = st.number_input(
                    f"{dish} 的數量", 
                    min_value=0, step=1, value=default_qty, 
                    key=f"q_{index}", 
                    label_visibility="collapsed"
                )
                st.write("") # 間距
            
            # 底部大按鈕
            submitted = st.form_submit_button("💾 送出訂單", type="primary")

        if submitted:
            # 更新邏輯
            clean_orders = orders_df[orders_df['name'] != st.session_state.user_name]
            new_rows = []
            for dish, qty in current_input.items():
                if qty > 0:
                    new_rows.append({"name": st.session_state.user_name, "item": dish, "qty": qty})
            
            final_df = pd.concat([clean_orders, pd.DataFrame(new_rows)], ignore_index=True)
            save_orders(final_df)
            st.toast("✅ 訂單已更新！")
            time.sleep(1)
            st.rerun()

# =======================
# Tab 2: 統計清單
# =======================
with tab2:
    if orders_df.empty:
        st.write("還沒人點餐。")
    else:
        merged = pd.merge(orders_df, menu_df, on="item", how="left")
        merged['subtotal'] = merged['qty'] * merged['price']
        
        # 1. 總金額
        total = merged['subtotal'].sum()
        st.metric("💰 總金額", f"${int(total)}")
        
        # 2. 廚房清單 (彙總)
        st.subheader("📋 廚房統計")
        summary = merged.groupby('item')['qty'].sum().reset_index()
        summary = summary[summary['qty'] > 0]
        st.dataframe(summary, use_container_width=True, hide_index=True)
        
        # 3. 誰點了什麼
        st.subheader("👤 詳細明細")
        for name, group in merged.groupby('name'):
            sub = group['subtotal'].sum()
            with st.expander(f"{name} (${int(sub)})"):
                for _, row in group.iterrows():
                    st.write(f"- {row['item']} x{row['qty']}")

        # 4. 重新整理按鈕
        if st.button("🔄 刷新最新狀態"):
            st.rerun()

# =======================
# Tab 3: 新增菜色
# =======================
with tab3:
    st.write("### 📸 AI 讀取菜單")
    uploaded_file = st.file_uploader("上傳照片", type=["jpg", "png", "jpeg"])
    
    if uploaded_file and st.button("✨ 開始解析"):
        with st.spinner("AI 處理中..."):
            try:
                img = Image.open(uploaded_file)
                model = genai.GenerativeModel(model_name="gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
                prompt = """
                識別菜單，輸出JSON list: [{"item": "菜名", "price": 數字}]。
                非繁體中文請翻譯。無價格填0。
                """
                resp = model.generate_content([prompt, img])
                data = json.loads(resp.text)
                
                new_df = pd.DataFrame(data)
                # 合併並去重
                combined = pd.concat([menu_df, new_df], ignore_index=True).drop_duplicates(subset=['item'], keep='last')
                save_menu(combined)
                st.success(f"新增 {len(data)} 道菜！")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"錯誤: {e}")

    st.write("---")
    st.write("### ✍️ 手動輸入")
    with st.form("add_manual"):
        name = st.text_input("菜名")
        price = st.number_input("價格", min_value=0)
        if st.form_submit_button("新增"):
            if name:
                row = pd.DataFrame([{"item": name, "price": price}])
                combined = pd.concat([menu_df, row], ignore_index=True).drop_duplicates(subset=['item'])
                save_menu(combined)
                st.success("已新增")
                st.rerun()