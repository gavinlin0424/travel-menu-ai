import streamlit as st
import pandas as pd
import time
from streamlit_gsheets import GSheetsConnection
from duckduckgo_search import DDGS

# --- 📱 手機版面設定 CSS ---
st.set_page_config(page_title="家族點餐", page_icon="🍱", layout="centered")

# 手機 Icon 設定
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
    /* 食記卡片樣式 */
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

# --- 資料庫操作 ---
def fetch_data():
    try:
        # ttl=5 表示快取 5 秒，確保多人使用時資料算即時
        menu_df = conn.read(worksheet="Menu", ttl=5)
        orders_df = conn.read(worksheet="Orders", ttl=5)
        
        # 確保欄位存在
        if 'shop' not in menu_df.columns: menu_df['shop'] = '未分類'
        if 'shop' not in orders_df.columns: orders_df['shop'] = '未分類'
        
        # 轉型
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

if menu_df.empty: menu_df = pd.DataFrame(columns=["shop", "item", "price"])
if orders_df.empty: orders_df = pd.DataFrame(columns=["name", "shop", "item", "qty"])

# 分頁定義 (修改順序與名稱)
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🍽️ 點餐", "📊 統計", "📸 新增店家", "🌏 找食記", "🛠️ 管理"])

# =======================
# Tab 1: 自由點餐 (手動輸入版)
# =======================
with tab1:
    st.info("💡 點擊下方店家，輸入你想吃的東西和價格。")
    
    if menu_df.empty:
        st.warning("目前沒有店家，請去「📸 新增店家」建立。")
    else:
        # 取得不重複的店家列表
        shops = menu_df['shop'].unique()
        
        for shop_name in shops:
            if not shop_name: continue
            
            # 使用 Expander 摺疊店家
            with st.expander(f"🏪 {shop_name}", expanded=False):
                with st.form(f"order_form_{shop_name}"):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    item_input = c1.text_input("品項", placeholder="例如：排骨飯")
                    price_input = c2.number_input("價格", min_value=0, step=1)
                    qty_input = c3.number_input("數量", min_value=1, value=1, step=1)
                    
                    if st.form_submit_button("➕ 加入訂單"):
                        if item_input and qty_input > 0:
                            new_row = {
                                "name": st.session_state.user_name,
                                "shop": shop_name,
                                "item": item_input, # 使用者自己輸入的品項
                                "qty": qty_input
                            }
                            # 讀取最新訂單並附加
                            current_orders = pd.concat([orders_df, pd.DataFrame([new_row])], ignore_index=True)
                            save_orders(current_orders)
                            st.toast(f"已幫 {st.session_state.user_name} 點了 {item_input}！")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("請輸入完整品項名稱！")

# =======================
# Tab 2: 統計與修改
# =======================
with tab2:
    if orders_df.empty:
        st.write("尚無訂單。")
    else:
        # 計算總金額 (這裡要小心，因為價格現在不在 Menu 表裡，而在使用者的腦袋裡)
        # 我們需要把 Orders 表裡的 item 跟 Menu 表關聯嗎？
        # 因為是「自由輸入」，價格是使用者自己打的，所以我們要在 Orders 表裡紀錄價格才對。
        # 但目前的架構是 Price 在 Menu 表。
        # 修正策略：這裡我們嘗試用 Menu 表去對應價格，如果找不到 (自由輸入的)，就假設價格為 0 或需要手動補。
        
        # 為了支援自由輸入，我們改成：統計時顯示清單，總金額可能需要人工算，或是我們改一下資料庫結構。
        # 簡單作法：這裡只統計數量，金額僅供參考 (如果有對應到 Menu 的話)
        
        merged = pd.merge(orders_df, menu_df, on=["shop", "item"], how="left")
        merged['price'] = merged['price'].fillna(0) # 沒對應到的價格補 0
        merged['subtotal'] = merged['qty'] * merged['price']
        
        # 1. 顯示廚房清單
        st.subheader("📋 彙總清單")
        for shop in merged['shop'].unique():
            with st.expander(f"🏪 {shop}", expanded=True):
                shop_data = merged[merged['shop'] == shop]
                # 依品項加總
                summary = shop_data.groupby('item')['qty'].sum().reset_index()
                st.table(summary)

        # 2. 個人明細
        st.divider()
        st.subheader("👤 個人明細")
        for name, group in merged.groupby('name'):
            with st.expander(f"{name}"):
                for _, row in group.iterrows():
                    price_display = f"${int(row['price'])}" if row['price'] > 0 else "價格自填"
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
# Tab 3: 新增店家 (改為建立分類)
# =======================
with tab3:
    st.write("### 🏪 建立新店家")
    st.info("輸入店家名稱後，大家就可以在「點餐」頁面看到這家店，並自由輸入想吃的東西。")
    
    new_shop_name = st.text_input("輸入店家名稱", placeholder="例如：巷口麵店")
    
    if st.button("✨ 建立店家"):
        if new_shop_name:
            # 建立一個「系統預設」的品項，讓店家出現在 Menu 表中
            new_row = pd.DataFrame([{"shop": new_shop_name, "item": "系統預設(勿刪)", "price": 0}])
            updated_menu = pd.concat([menu_df, new_row], ignore_index=True).drop_duplicates(subset=['shop', 'item'])
            save_menu(updated_menu)
            st.success(f"已建立【{new_shop_name}】！請到點餐頁面開始點餐。")
            time.sleep(1)
            st.rerun()
        else:
            st.error("請輸入店名！")

# =======================
# Tab 4: 找食記 (新功能)
# =======================
with tab4:
    st.write("### 🌏 搜尋食記與評價")
    query_shop = st.text_input("輸入想查的餐廳/食物", placeholder="例如：台南 阿堂鹹粥")
    
    if st.button("🔍 搜尋"):
        if query_shop:
            with st.spinner("正在搜尋部落客食記與 Google 評價..."):
                try:
                    # 搜尋 "食記" 和 "菜單" 關鍵字
                    results = DDGS().text(f"{query_shop} 食記 菜單 評價 dcard ptt", max_results=8)
                    
                    if results:
                        for r in results:
                            # 顯示卡片式搜尋結果
                            st.markdown(f"""
                            <div class="review-card">
                                <a href="{r['href']}" target="_blank">{r['title']}</a>
                                <p>{r['body']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.warning("找不到相關結果，請換個關鍵字試試。")
                except Exception as e:
                    st.error(f"搜尋發生錯誤: {e}")

# =======================
# Tab 5: 管理
# =======================
with tab5:
    st.write("### 🛠️ 店家與菜單管理")
    st.caption("如果要刪除店家，請把該店家的所有項目都刪除。")
    
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