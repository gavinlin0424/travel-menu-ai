import streamlit as st
import pandas as pd
import json
import time
from streamlit_gsheets import GSheetsConnection
from duckduckgo_search import DDGS

# --- 📱 手機版面設定 CSS ---
st.set_page_config(page_title="家族點餐", page_icon="🍱", layout="centered")

# Icon 設定
icon_url = "https://github.com/gavinlin0424/travel-menu-ai/blob/a0eb070625c2249f21bdcc11b3bee24eb68183ed/app_icon.png"
st.markdown(f"""
    <head>
        <link rel="apple-touch-icon" sizes="180x180" href="{icon_url}">
        <link rel="icon" type="image/png" sizes="32x32" href="{icon_url}">
        <link rel="manifest" href="/site.webmanifest">
    </head>
    <style>
    html, body, [class*="css"] {{ font-family: 'Heiti TC', 'Microsoft JhengHei', sans-serif; }}
    button[data-baseweb="tab"] {{ font-size: 16px !important; padding: 10px !important; flex: 1; }}
    input[type="number"] {{ font-size: 18px !important; text-align: center; }}
    .stButton > button {{ width: 100%; border-radius: 8px; font-weight: bold; padding: 10px; }}
    .streamlit-expanderHeader {{ font-size: 18px; font-weight: bold; background-color: #fff3e0; color: #e65100; border-radius: 5px; }}
    
    /* 食記卡片 */
    div.review-card {{
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }}
    div.review-card a {{ text-decoration: none; color: #1a73e8; font-weight: bold; font-size: 16px; }}
    div.review-card p {{ color: #555; font-size: 14px; margin-top: 5px; }}
    </style>
""", unsafe_allow_html=True)

# --- 連線設定 ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.error("連線錯誤，請檢查 Secrets 設定")
    st.stop()

# --- 資料庫操作 (加上防呆機制) ---
def fetch_data():
    try:
        # ttl=5 表示快取 5 秒
        menu_df = conn.read(worksheet="Menu", ttl=5)
        orders_df = conn.read(worksheet="Orders", ttl=5)
        
        # 確保欄位存在
        if 'shop' not in menu_df.columns: menu_df['shop'] = '未分類'
        if 'shop' not in orders_df.columns: orders_df['shop'] = '未分類'
        
        # 轉型
        menu_df['price'] = pd.to_numeric(menu_df['price'], errors='coerce').fillna(0).astype(int)
        return menu_df, orders_df
        
    except Exception as e:
        # 如果讀取失敗，回傳空的表格，避免程式崩潰跳頁
        # st.error(f"讀取資料庫失敗: {e}") # Debug用，若想畫面乾淨可註解
        return pd.DataFrame(columns=["shop", "item", "price"]), pd.DataFrame(columns=["name", "shop", "item", "qty"])

def save_menu(df):
    try:
        conn.update(worksheet="Menu", data=df)
    except Exception as e:
        st.error(f"寫入失敗 (Menu): {e}")

def save_orders(df):
    try:
        conn.update(worksheet="Orders", data=df)
    except Exception as e:
        st.error(f"寫入失敗 (Orders): {e}")

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
col1, col2 = st.columns([3, 1]) 
with col1:
    st.write(f"### 👋 Hi, {st.session_state.user_name}")
with col2:
    if st.button("🔄 換人", type="secondary"):
        st.session_state.user_name = ""
        st.rerun()

menu_df, orders_df = fetch_data()
menu_df = menu_df.fillna("")
orders_df = orders_df.fillna("")

# 🔴 錯誤偵測顯示區 (如果第一張截圖的 Menu 錯誤還在，這裡會提示)
if menu_df.empty and orders_df.empty:
    st.warning("⚠️ 警告：目前讀不到任何資料。請確認 Google 試算表下方分頁名稱是否為「Menu」和「Orders」(大小寫需一致)。")

# 分頁定義
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🍽️ 點餐", "📊 統計", "📸 新增店家", "🌏 找食記", "🛠️ 管理"])

# =======================
# Tab 1: 自由點餐
# =======================
with tab1:
    st.info("💡 點擊下方店家，輸入你想吃的東西。")
    
    if menu_df.empty:
        st.warning("目前沒有店家。")
    else:
        shops = menu_df['shop'].unique()
        for shop_name in shops:
            if not shop_name: continue
            
            with st.expander(f"🏪 {shop_name}", expanded=False):
                # 使用 form 防止每次輸入就跳轉
                with st.form(f"order_form_{shop_name}"):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    item_input = c1.text_input("品項", placeholder="例如：雞排")
                    price_input = c2.number_input("價格", min_value=0, step=1)
                    qty_input = c3.number_input("數量", min_value=1, value=1, step=1)
                    
                    if st.form_submit_button("➕ 加入訂單"):
                        if item_input:
                            new_row = {
                                "name": st.session_state.user_name,
                                "shop": shop_name,
                                "item": item_input,
                                "qty": qty_input,
                                "price": price_input # 這裡暫存價格，雖然統計有點複雜，但先存起來
                            }
                            # 重新讀取確保不蓋掉別人的
                            current_menu, current_orders = fetch_data()
                            updated_orders = pd.concat([current_orders, pd.DataFrame([new_row])], ignore_index=True)
                            save_orders(updated_orders)
                            st.toast(f"已幫 {st.session_state.user_name} 點了 {item_input}！")
                            time.sleep(1)
                            st.rerun()

# =======================
# Tab 2: 統計
# =======================
with tab2:
    if orders_df.empty:
        st.write("尚無訂單。")
    else:
        # 簡易統計邏輯
        # 嘗試將 Menu 的價格合併進來 (如果是預設菜單)
        # 如果 Menu 沒價格，就看 Orders 裡面有沒有填價格
        merged = pd.merge(orders_df, menu_df, on=["shop", "item"], how="left", suffixes=('', '_menu'))
        
        # 優先使用 Menu 的價格，如果沒有則使用訂單輸入的價格
        merged['final_price'] = merged['price_menu'].fillna(0)
        # 如果 Menu 價格是 0 (自由輸入)，嘗試拿使用者輸入的 price (如果有存的話，目前架構 orders 表沒 price 欄位，需依賴上一版結構)
        # 為了簡化，我們主要統計數量
        
        st.subheader("📋 彙總清單")
        for shop in merged['shop'].unique():
            with st.expander(f"🏪 {shop}", expanded=True):
                shop_data = merged[merged['shop'] == shop]
                summary = shop_data.groupby('item')['qty'].sum().reset_index()
                st.table(summary)

        st.divider()
        st.subheader("👤 個人明細")
        for name, group in merged.groupby('name'):
            with st.expander(f"{name}"):
                for _, row in group.iterrows():
                    st.write(f"• [{row['shop']}] **{row['item']}** x{row['qty']}")

    st.write("---")
    st.write("### 🛠️ 修改訂單")
    edited_orders = st.data_editor(
        orders_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name": st.column_config.TextColumn("名字"),
            "shop": st.column_config.TextColumn("店家"),
            "item": st.column_config.TextColumn("品項"),
            "qty": st.column_config.NumberColumn("數量")
        },
        key="order_editor"
    )
    
    if st.button("💾 儲存修改"):
        save_orders(edited_orders)
        st.success("已更新！")
        time.sleep(1)
        st.rerun()

# =======================
# Tab 3: 新增店家
# =======================
with tab3:
    st.write("### 🏪 建立新店家")
    with st.form("add_shop_form"):
        new_shop_name = st.text_input("輸入店家名稱", placeholder="例如：巷口麵店")
        submit_shop = st.form_submit_button("✨ 建立店家")
        
    if submit_shop:
        if new_shop_name:
            new_row = pd.DataFrame([{"shop": new_shop_name, "item": "系統預設(勿刪)", "price": 0}])
            # 先讀取最新 Menu
            cur_menu, _ = fetch_data()
            updated_menu = pd.concat([cur_menu, new_row], ignore_index=True).drop_duplicates(subset=['shop', 'item'])
            save_menu(updated_menu)
            st.success(f"已建立【{new_shop_name}】！")
            time.sleep(1)
            st.rerun()
        else:
            st.error("請輸入店名！")

# =======================
# Tab 4: 找食記 (修正版)
# =======================
with tab4:
    st.write("### 🌏 搜尋食記與評價")
    
    # 使用 Form 避免輸入時一直跳轉
    with st.form("search_reviews_form"):
        query_shop = st.text_input("輸入想查的餐廳/食物", placeholder="例如：台東 阿鋐炸雞")
        search_btn = st.form_submit_button("🔍 搜尋")

    if search_btn and query_shop:
        st.info(f"正在搜尋：{query_shop}...")
        
        # 1. 提供直接連結 (保底方案，絕對不會失敗)
        google_url = f"https://www.google.com/search?q={query_shop}+食記+菜單+dcard"
        st.markdown(f"""
            <a href="{google_url}" target="_blank" style="display:block; background-color:#4285F4; color:white; text-align:center; padding:12px; border-radius:8px; text-decoration:none; font-weight:bold; margin-bottom:15px;">
                👉 點此直接前往 Google 搜尋 (最準確)
            </a>
        """, unsafe_allow_html=True)
        
        # 2. 嘗試用 DuckDuckGo 抓取內容 (可能會失敗，所以用 try 包起來)
        try:
            results = DDGS().text(f"{query_shop} 食記 菜單 評價 dcard ptt", max_results=5)
            if results:
                st.write("🔎 快速預覽結果：")
                for r in results:
                    st.markdown(f"""
                    <div class="review-card">
                        <a href="{r['href']}" target="_blank">{r['title']}</a>
                        <p>{r['body']}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("自動抓取無結果，請使用上方藍色按鈕直接搜尋。")
        except Exception as e:
            st.caption("自動抓取受限 (IP 限制)，請使用上方藍色按鈕直接搜尋。")

# =======================
# Tab 5: 管理
# =======================
with tab5:
    st.write("### 🛠️ 店家與菜單管理")
    edited_menu = st.data_editor(
        menu_df,
        num_rows="dynamic", 
        use_container_width=True,
        key="menu_mgr"
    )

    if st.button("💾 儲存設定"):
        save_menu(edited_menu)
        st.success("已更新！")
        time.sleep(1)
        st.rerun()