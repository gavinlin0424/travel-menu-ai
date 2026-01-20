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
        flex: 1; 
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
        padding: 10px;
    }
    
    /* 卡片樣式 */
    div.dish-card {
        background-color: #f0f2f6;
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 8px;
        border: 1px solid #e0e0e0;
    }
    
    /* Expander 樣式 */
    .streamlit-expanderHeader {
        font-size: 18px;
        font-weight: bold;
        background-color: #fff3e0;
        color: #e65100;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 連線設定 ---
api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key: st.stop()
genai.configure(api_key=api_key)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("連線錯誤，請檢查 Secrets")
    st.stop()

# --- 資料庫操作 ---
def fetch_data():
    try:
        # ttl=0 確保每次都抓最新資料
        menu_df = conn.read(worksheet="Menu", ttl=0)
        orders_df = conn.read(worksheet="Orders", ttl=0)
        
        # 補齊欄位
        if 'shop' not in menu_df.columns: menu_df['shop'] = '未分類'
        if 'shop' not in orders_df.columns: orders_df['shop'] = '未分類'
        
        # 轉型確保價格是數字 (編輯時才不會報錯)
        menu_df['price'] = pd.to_numeric(menu_df['price'], errors='coerce').fillna(0).astype(int)
        
    except:
        menu_df = pd.DataFrame(columns=["shop", "item", "price"])
        orders_df = pd.DataFrame(columns=["name", "shop", "item", "qty"])
    return menu_df, orders_df

def save_menu(df):
    conn.update(worksheet="Menu", data=df)

def save_orders(df):
    conn.update(worksheet="Orders", data=df)

# --- 👋 登入畫面 ---
if "user_name" not in st.session_state or not st.session_state.user_name:
    st.title("🍱 家族點餐")
    name_input = st.text_input("輸入名字開始：", placeholder="例如：爸爸")
    if st.button("🚀 進入", type="primary"):
        if name_input.strip():
            st.session_state.user_name = name_input.strip()
            st.rerun()
    st.stop()

# --- 主程式 ---
st.caption(f"👤 身份：{st.session_state.user_name}")
menu_df, orders_df = fetch_data()

# 補強空值
menu_df = menu_df.fillna("")
orders_df = orders_df.fillna("")

if menu_df.empty: menu_df = pd.DataFrame(columns=["shop", "item", "price"])
if orders_df.empty: orders_df = pd.DataFrame(columns=["name", "shop", "item", "qty"])

# 定義 4 個分頁
tab1, tab2, tab3, tab4 = st.tabs(["🍽️ 點餐", "📊 統計", "📸 加菜", "🛠️ 管理"])

# =======================
# Tab 1: 點餐 (支援摺疊收納)
# =======================
with tab1:
    if menu_df.empty:
        st.info("目前沒有菜單，請去「📸 加菜」或「🛠️ 管理」新增。")
    else:
        # 準備舊訂單 map
        my_orders = orders_df[orders_df['name'] == st.session_state.user_name]
        my_order_map = {}
        for _, r in my_orders.iterrows():
            key = f"{r['shop']}_{r['item']}"
            my_order_map[key] = r['qty']
        
        current_input = {}
        
        with st.form("order_form"):
            shops = menu_df['shop'].unique()
            
            for shop_name in shops:
                if not shop_name: continue
                
                shop_menu = menu_df[menu_df['shop'] == shop_name]
                item_count = len(shop_menu)
                
                with st.expander(f"🏪 {shop_name} ({item_count})", expanded=True):
                    for index, row in shop_menu.iterrows():
                        dish = row['item']
                        price = row['price']
                        unique_key = f"{shop_name}_{dish}"
                        default_qty = int(my_order_map.get(unique_key, 0))
                        
                        st.markdown(f"""
                        <div class="dish-card">
                            <div style="display:flex; justify-content:space-between;">
                                <b>{dish}</b>
                                <span style="color:#666;">${price}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        current_input[unique_key] = st.number_input(
                            f"數量", min_value=0, step=1, value=default_qty, 
                            key=f"q_{unique_key}", label_visibility="collapsed"
                        )
            
            st.write("")
            submitted = st.form_submit_button("💾 送出訂單", type="primary")

        if submitted:
            clean_orders = orders_df[orders_df['name'] != st.session_state.user_name]
            new_rows = []
            for unique_key, qty in current_input.items():
                if qty > 0:
                    shop_val, item_val = unique_key.split("_", 1)
                    new_rows.append({
                        "name": st.session_state.user_name,
                        "shop": shop_val,
                        "item": item_val,
                        "qty": qty
                    })
            
            final_df = pd.concat([clean_orders, pd.DataFrame(new_rows)], ignore_index=True)
            save_orders(final_df)
            st.toast("✅ 訂單已更新！")
            time.sleep(1)
            st.rerun()

# =======================
# Tab 2: 統計
# =======================
with tab2:
    if orders_df.empty:
        st.write("尚無訂單。")
    else:
        merged = pd.merge(orders_df, menu_df, on=["shop", "item"], how="left")
        merged['subtotal'] = merged['qty'] * merged['price']
        
        total = merged['subtotal'].sum()
        st.metric("💰 總金額", f"${int(total)}")
        
        st.subheader("📋 廚房準備清單")
        shops_in_order = merged['shop'].unique()
        for shop in shops_in_order:
            with st.expander(f"🏪 {shop}", expanded=True):
                shop_data = merged[merged['shop'] == shop]
                summary = shop_data.groupby('item')['qty'].sum().reset_index()
                summary = summary[summary['qty'] > 0]
                st.table(summary)
            
        st.divider()
        st.subheader("👤 個人結帳明細")
        for name, group in merged.groupby('name'):
            p_total = group['subtotal'].sum()
            with st.expander(f"{name} (${int(p_total)})"):
                for _, row in group.iterrows():
                    st.write(f"[{row['shop']}] {row['item']} x{row['qty']}")

        if st.button("🔄 刷新"): st.rerun()

# =======================
# Tab 3: AI 加菜
# =======================
with tab3:
    st.write("### 📸 拍照新增")
    
    shop_name_input = st.text_input("🏪 店家名稱", placeholder="例如：50嵐")
    uploaded_file = st.file_uploader("上傳菜單照片", type=["jpg", "png", "jpeg"])
    
    if uploaded_file and st.button("✨ 開始解析"):
        if not shop_name_input:
            st.error("⚠️ 請輸入店家名稱！")
        else:
            with st.spinner(f"正在讀取【{shop_name_input}】的菜單..."):
                try:
                    img = Image.open(uploaded_file)
                    model = genai.GenerativeModel(
                        model_name="gemini-2.5-flash", 
                        generation_config={"response_mime_type": "application/json"}
                    )
                    prompt = """
                    你是一個台灣在地導遊與翻譯。請分析這張菜單圖片：
                    1. 識別所有菜色與價格。
                    2. 【重要】所有菜名一律翻譯成「台灣習慣的繁體中文」。
                    3. 不要保留外文原文。
                    4. 輸出 JSON list: [{"item": "中文菜名", "price": 數字}]。
                    5. 價格不明填 0。
                    """

                    resp = model.generate_content([prompt, img])
                    data = json.loads(resp.text)
                    
                    new_df = pd.DataFrame(data)
                    new_df['shop'] = shop_name_input
                    new_df = new_df[['shop', 'item', 'price']]
                    
                    combined = pd.concat([menu_df, new_df], ignore_index=True)
                    combined = combined.drop_duplicates(subset=['shop', 'item'], keep='last')
                    
                    save_menu(combined)
                    st.success(f"成功新增 {len(data)} 道菜！")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"解析失敗: {e}")

# =======================
# Tab 4: 菜單管理 (新增編輯功能)
# =======================
with tab4:
    st.write("### 🛠️ 編輯與刪除菜單")
    st.info("💡 這裡像 Excel 一樣，可以直接點兩下修改，或勾選刪除。改完記得按下面的儲存按鈕！")

    # 使用 data_editor 進行編輯
    # num_rows="dynamic" 讓使用者可以自己按 + 新增列
    edited_df = st.data_editor(
        menu_df,
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "shop": st.column_config.TextColumn("店家名稱", help="例如：50嵐"),
            "item": st.column_config.TextColumn("菜色名稱", help="例如：紅茶"),
            "price": st.column_config.NumberColumn("價格", format="$%d")
        },
        key="menu_editor"
    )

    if st.button("💾 儲存所有變更 (包含刪除與修改)", type="primary"):
        try:
            # 存回 Google Sheets
            save_menu(edited_df)
            st.success("✅ 菜單已更新！")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"儲存失敗: {e}")