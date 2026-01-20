import streamlit as st
import pandas as pd
import json
import time
from PIL import Image
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
from duckduckgo_search import DDGS  # 引入搜尋工具

# --- 📱 手機版面設定 CSS ---
st.set_page_config(page_title="點餐", page_icon="🍱", layout="centered")

# --- 設定手機主畫面圖示 ---
icon_url = "https://github.com/gavinlin0424/travel-menu-ai/blob/a0eb070625c2249f21bdcc11b3bee24eb68183ed/app_icon.png"
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
st.markdown(f'<img src="{icon_url}" style="display:none;">', unsafe_allow_html=True)

st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: 'Heiti TC', 'Microsoft JhengHei', sans-serif; }
    button[data-baseweb="tab"] { font-size: 16px !important; padding: 10px !important; flex: 1; }
    input[type="number"] { font-size: 18px !important; text-align: center; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; padding: 10px; }
    div.dish-card { background-color: #f0f2f6; padding: 10px 15px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #e0e0e0; }
    .streamlit-expanderHeader { font-size: 18px; font-weight: bold; background-color: #fff3e0; color: #e65100; border-radius: 5px; }
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
        menu_df = conn.read(worksheet="Menu", ttl=0)
        orders_df = conn.read(worksheet="Orders", ttl=0)
        if 'shop' not in menu_df.columns: menu_df['shop'] = '未分類'
        if 'shop' not in orders_df.columns: orders_df['shop'] = '未分類'
        menu_df['price'] = pd.to_numeric(menu_df['price'], errors='coerce').fillna(0).astype(int)
    except:
        menu_df = pd.DataFrame(columns=["shop", "item", "price"])
        orders_df = pd.DataFrame(columns=["name", "shop", "item", "qty"])
    return menu_df, orders_df

def save_menu(df):
    conn.update(worksheet="Menu", data=df)

def save_orders(df):
    conn.update(worksheet="Orders", data=df)

# --- 搜尋功能函式 ---
def search_menu_on_web(query):
    """使用 DuckDuckGo 搜尋菜單文字資訊"""
    try:
        results = DDGS().text(f"{query} 菜單 價格 2024 2025", max_results=5)
        search_content = "\n".join([f"標題: {r['title']}\n內容: {r['body']}" for r in results])
        return search_content
    except Exception as e:
        return None

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
# --- 主程式 (修改這裡：增加快速換人按鈕) ---
# 使用 col1, col2 把「歡迎詞」和「換人按鈕」排在同一排
col1, col2 = st.columns([3, 1]) 

with col1:
    st.write(f"### 👋 Hi, {st.session_state.user_name}")

with col2:
    # 這裡加入換人按鈕
    if st.button("🔄 換人", type="secondary"):
        st.session_state.user_name = "" # 清空名字
        st.rerun() # 重新執行，會自動跳回輸入名字的畫面

# 讀取資料
menu_df, orders_df = fetch_data()
menu_df = menu_df.fillna("")
orders_df = orders_df.fillna("")

if menu_df.empty: menu_df = pd.DataFrame(columns=["shop", "item", "price"])
if orders_df.empty: orders_df = pd.DataFrame(columns=["name", "shop", "item", "qty"])

# 定義 5 個分頁 (修改 Tab 3 名稱，並在 Tab 2 增加功能)
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🍽️ 點餐", "📊 統計/修改", "📸 新增菜單", "🔍 搜尋", "🛠️ 菜單管理"])

COMMON_PROMPT = """
你是一個菜單整理助手。請依照以下規則提取菜單：
1. 識別所有菜色與價格。
2. 【絕對規則】如果菜名原本就是繁體中文（例如：「冷露」、「春芽」、「歐蕾」），請「完整保留原文」，絕對不要翻譯成白話文（不要改成冬瓜茶、綠茶、拿鐵）。
3. 只有當原文是外文（英/日/韓）時，才翻譯成台灣習慣的繁體中文。
4. 輸出 JSON list: [{"item": "菜名", "price": 數字}]。
5. 價格不明填 0。
"""

# =======================
# Tab 1: 點餐
# =======================
with tab1:
    if menu_df.empty:
        st.info("目前沒有菜單，請去「📸 新增菜單」或「🔍 搜尋」新增。")
    else:
        my_orders = orders_df[orders_df['name'] == st.session_state.user_name]
        my_order_map = {f"{r['shop']}_{r['item']}": r['qty'] for _, r in my_orders.iterrows()}
        current_input = {}
        
        with st.form("order_form"):
            shops = menu_df['shop'].unique()
            for shop_name in shops:
                if not shop_name: continue
                shop_menu = menu_df[menu_df['shop'] == shop_name]
                
                with st.expander(f"🏪 {shop_name} ({len(shop_menu)})", expanded=True):
                    for _, row in shop_menu.iterrows():
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
            if st.form_submit_button("💾 送出訂單", type="primary"):
                clean_orders = orders_df[orders_df['name'] != st.session_state.user_name]
                new_rows = []
                for k, qty in current_input.items():
                    if qty > 0:
                        s, i = k.split("_", 1)
                        new_rows.append({"name": st.session_state.user_name, "shop": s, "item": i, "qty": qty})
                save_orders(pd.concat([clean_orders, pd.DataFrame(new_rows)], ignore_index=True))
                st.toast("✅ 訂單已更新！")
                time.sleep(1)
                st.rerun()

# =======================
# Tab 2: 統計 (新增修改功能)
# =======================
with tab2:
    if orders_df.empty:
        st.write("尚無訂單。")
    else:
        merged = pd.merge(orders_df, menu_df, on=["shop", "item"], how="left")
        merged['subtotal'] = merged['qty'] * merged['price']
        st.metric("💰 總金額", f"${int(merged['subtotal'].sum())}")
        
        st.subheader("📋 廚房準備清單")
        for shop in merged['shop'].unique():
            with st.expander(f"🏪 {shop}", expanded=True):
                shop_data = merged[merged['shop'] == shop]
                summary = shop_data.groupby('item')['qty'].sum().reset_index()
                st.table(summary[summary['qty'] > 0])
        
        st.divider()
        st.subheader("👤 個人明細")
        for name, group in merged.groupby('name'):
            with st.expander(f"{name} (${int(group['subtotal'].sum())})"):
                for _, row in group.iterrows():
                    st.write(f"[{row['shop']}] {row['item']} x{row['qty']}")
    
    st.write("---")
    st.write("### 🛠️ 修改/刪除訂單")
    st.info("💡 如果有人點錯，或是要幫忙調整數量，請在下方直接修改，改完記得按「儲存」。")
    
    # 使用 data_editor 讓使用者直接編輯 orders_df
    edited_orders = st.data_editor(
        orders_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name": st.column_config.TextColumn("點餐人"),
            "shop": st.column_config.TextColumn("店家"),
            "item": st.column_config.TextColumn("品項"),
            "qty": st.column_config.NumberColumn("數量")
        },
        key="order_editor" # 給它一個 Key 避免狀態跑掉
    )
    
    if st.button("💾 儲存訂單修改 (Tab 2)"):
        save_orders(edited_orders)
        st.success("訂單紀錄已更新！")
        time.sleep(1)
        st.rerun()

# =======================
# Tab 3: 拍照新增 (修正跳轉問題)
# =======================
with tab3:
    st.write("### 📸 新增菜單") # 已改名
    shop_input = st.text_input("🏪 店家名稱 (拍照)", placeholder="例如：50嵐")
    
    # 【關鍵修正】加上 key="upload_menu_img" 避免上傳後跳回 Tab 1
    uploaded_file = st.file_uploader("上傳菜單照片", type=["jpg", "png", "jpeg"], key="upload_menu_img")
    
    if uploaded_file and st.button("✨ 解析照片"):
        if not shop_input:
            st.error("請輸入店家名稱！")
        else:
            with st.spinner(f"正在看【{shop_input}】的菜單..."):
                try:
                    img = Image.open(uploaded_file)
                    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
                    resp = model.generate_content([COMMON_PROMPT, img])
                    
                    new_df = pd.DataFrame(json.loads(resp.text))
                    new_df['shop'] = shop_input
                    new_df = new_df[['shop', 'item', 'price']]
                    
                    save_menu(pd.concat([menu_df, new_df], ignore_index=True).drop_duplicates(subset=['shop', 'item'], keep='last'))
                    st.success(f"新增成功！")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"解析失敗: {e}")

# =======================
# Tab 4: 搜尋新增
# =======================
with tab4:
    st.write("### 🔍 AI 搜尋菜單")
    st.info("輸入店名，AI 會去網路上找菜單。")
    
    search_shop_name = st.text_input("🔍 請輸入店家名稱", placeholder="例如：可不可熟成紅茶")
    
    if st.button("🕷️ 開始搜尋並建立菜單"):
        if not search_shop_name:
            st.error("請輸入店名！")
        else:
            with st.spinner(f"正在網路上搜尋【{search_shop_name}】的菜單與食記..."):
                web_content = search_menu_on_web(search_shop_name)
                
                if not web_content:
                    st.warning("搜尋不到資料，嘗試使用 AI 內建知識庫...")
                    web_content = f"請根據你的知識庫列出 {search_shop_name} 的菜單。"
                
                try:
                    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
                    full_prompt = f"""
                    以下是關於「{search_shop_name}」的網路搜尋結果或食記：
                    {web_content}
                    請根據以上資訊整理出菜單。
                    {COMMON_PROMPT}
                    """
                    resp = model.generate_content(full_prompt)
                    items = json.loads(resp.text)
                    
                    if items:
                        new_df = pd.DataFrame(items)
                        new_df['shop'] = search_shop_name
                        new_df = new_df[['shop', 'item', 'price']]
                        
                        save_menu(pd.concat([menu_df, new_df], ignore_index=True).drop_duplicates(subset=['shop', 'item'], keep='last'))
                        st.success(f"搜尋完畢！找到 {len(items)} 道菜")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.warning("AI 找不到完整的菜單資訊，請試著手動輸入或上傳照片。")
                        
                except Exception as e:
                    st.error(f"搜尋整理失敗: {e}")

# =======================
# Tab 5: 管理
# =======================
with tab5:
    st.write("### 🛠️ 編輯菜單")
    edited_df = st.data_editor(
        menu_df,
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "shop": st.column_config.TextColumn("店家"),
            "item": st.column_config.TextColumn("菜名"),
            "price": st.column_config.NumberColumn("價格", format="$%d")
        },
        key="menu_editor"
    )

    if st.button("💾 儲存菜單變更"):
        save_menu(edited_df)
        st.success("已更新！")
        time.sleep(1)
        st.rerun()