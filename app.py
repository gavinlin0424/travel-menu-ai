import streamlit as st
import pandas as pd
import json
import time
from PIL import Image
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# --- 頁面設定 ---
st.set_page_config(page_title="線上點餐", page_icon="🍱", layout="centered")
st.title("🍱 旅遊點餐")

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


# --- 連線設定 ---
# 1. 取得 AI Key
api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key:
    st.error("❌ 缺少 Google API Key")
    st.stop()
genai.configure(api_key=api_key)

# 2. 建立 Google Sheets 連線
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 讀取資料庫函式 (Read) ---
def fetch_data():
    # 讀取試算表，我們假設 Worksheet 0 是菜單(Menu)，Worksheet 1 是訂單(Orders)
    # 如果是第一次建立，會自動產生空的 DataFrame
    try:
        menu_df = conn.read(worksheet="Menu", ttl=0) # ttl=0 代表不快取，每次都重新抓
        orders_df = conn.read(worksheet="Orders", ttl=0)
    except:
        # 如果試算表是空的，初始化它
        menu_df = pd.DataFrame(columns=["item", "price"])
        orders_df = pd.DataFrame(columns=["name", "item", "qty"])
    return menu_df, orders_df

# --- 寫入資料庫函式 (Write) ---
def save_menu(df):
    conn.update(worksheet="Menu", data=df)

def save_orders(df):
    conn.update(worksheet="Orders", data=df)

# --- 身份確認 ---
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

with st.sidebar:
    st.header("👤 你的身份")
    name_input = st.text_input("請輸入你的名字 (必填)", value=st.session_state.user_name)
    if name_input:
        st.session_state.user_name = name_input
        st.success(f"哈囉，{name_input}！")
    else:
        st.warning("請先輸入名字才能點餐喔！")
        st.stop() # 沒名字不給用

    if st.button("🔄 重新整理資料"):
        st.rerun()

# --- 讀取最新資料 ---
menu_df, orders_df = fetch_data()

# 確保欄位正確 (避免空表格報錯)
if menu_df.empty:
    menu_df = pd.DataFrame(columns=["item", "price"])
if orders_df.empty:
    orders_df = pd.DataFrame(columns=["name", "item", "qty"])

# --- Tab 分頁設計 ---
tab1, tab2, tab3 = st.tabs(["🍽️ 點餐區", "📊 統計總覽", "📸 新增菜色"])

# ====================
# Tab 3: 新增菜色 (AI + 手動)
# ====================
with tab3:
    st.subheader("新增菜單項目")
    
    # A. 手動新增
    with st.expander("➕ 手動輸入一道菜"):
        with st.form("manual_add"):
            c1, c2 = st.columns([3, 1])
            new_item = c1.text_input("菜名")
            new_price = c2.number_input("價格", min_value=0, step=10)
            if st.form_submit_button("新增到菜單"):
                new_row = pd.DataFrame([{"item": new_item, "price": new_price}])
                updated_menu = pd.concat([menu_df, new_row], ignore_index=True).drop_duplicates(subset=['item'])
                save_menu(updated_menu)
                st.success(f"已新增：{new_item}")
                time.sleep(1)
                st.rerun()

    # B. AI 解析
    st.write("---")
    st.write("🤖 **AI 自動解析照片**")
    uploaded_file = st.file_uploader("上傳菜單照片", type=["jpg", "png", "jpeg"])
    
    if uploaded_file and st.button("✨ 啟動 AI 解析"):
        with st.spinner("Gemini 正在讀取菜單並寫入資料庫..."):
            image = Image.open(uploaded_file)
            
            # 呼叫 Gemini 2.5
            model = genai.GenerativeModel(model_name="gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
            prompt = """
            分析菜單圖片，輸出 JSON list: [{"item": "菜名", "price": 數字}, ...]。
            非繁體中文請翻譯。無價格填0。
            """
            try:
                response = model.generate_content([prompt, image])
                ai_items = json.loads(response.text)
                
                # 轉換為 DataFrame 並與現有菜單合併
                new_menu_df = pd.DataFrame(ai_items)
                # 合併邏輯：保留舊的，加入新的，去除重複菜名
                combined_menu = pd.concat([menu_df, new_menu_df], ignore_index=True).drop_duplicates(subset=['item'], keep='last')
                
                save_menu(combined_menu)
                st.success(f"成功識別 {len(ai_items)} 道菜！")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"解析失敗: {e}")

# ====================
# Tab 1: 點餐區
# ====================
with tab1:
    if menu_df.empty:
        st.info("目前菜單是空的，請到「新增菜色」分頁上傳照片或手動新增。")
    else:
        st.subheader(f"👋 {st.session_state.user_name}，請點餐：")
        
        # 預先抓取該使用者已經點過的數量
        my_orders = orders_df[orders_df['name'] == st.session_state.user_name]
        # 轉成字典方便查找: {'牛肉麵': 1, '紅茶': 2}
        my_order_map = dict(zip(my_orders['item'], my_orders['qty']))
        
        # 暫存當前頁面的輸入
        current_input = {}

        with st.form("ordering_form"):
            for index, row in menu_df.iterrows():
                dish_name = row['item']
                price = row['price']
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{dish_name}** (${price})")
                with col2:
                    # 預設值顯示之前點過的數量
                    default_qty = int(my_order_map.get(dish_name, 0))
                    current_input[dish_name] = st.number_input(
                        "數量", min_value=0, step=1, value=default_qty, key=f"q_{index}", label_visibility="collapsed"
                    )
            
            # 送出按鈕
            submitted = st.form_submit_button("💾 儲存/更新我的訂單")

        if submitted:
            # 1. 刪除該使用者舊的所有訂單 (清空重寫策略)
            clean_orders_df = orders_df[orders_df['name'] != st.session_state.user_name]
            
            # 2. 整理新的訂單
            new_order_rows = []
            for dish, qty in current_input.items():
                if qty > 0:
                    new_order_rows.append({
                        "name": st.session_state.user_name,
                        "item": dish,
                        "qty": qty
                    })
            
            # 3. 合併並寫入 Google Sheets
            if new_order_rows:
                final_df = pd.concat([clean_orders_df, pd.DataFrame(new_order_rows)], ignore_index=True)
            else:
                final_df = clean_orders_df # 如果全部改成0，就等於只刪除
            
            save_orders(final_df)
            st.toast("✅ 訂單已更新！", icon="🎉")
            time.sleep(1)
            st.rerun()

# ====================
# Tab 2: 統計總覽 (大家都能看)
# ====================
with tab2:
    st.subheader("📊 大家點了什麼？")
    
    if orders_df.empty:
        st.write("目前還沒有人點餐。")
    else:
        # 合併價格資訊 (Orders Join Menu)
        merged_df = pd.merge(orders_df, menu_df, on="item", how="left")
        merged_df['subtotal'] = merged_df['qty'] * merged_df['price']
        
        # 1. 依照「菜色」統計 (給店家看)
        st.markdown("### 👨‍🍳 廚房清單 (依菜色)")
        item_summary = merged_df.groupby('item')['qty'].sum().reset_index()
        item_summary = item_summary[item_summary['qty'] > 0] # 只顯示有點的
        st.dataframe(item_summary, use_container_width=True)
        
        # 2. 依照「人」統計 (結帳用)
        st.divider()
        st.markdown("### 💰 結帳清單 (依人名)")
        
        # 顯示每個人的明細
        for name, group in merged_df.groupby('name'):
            person_total = group['subtotal'].sum()
            with st.expander(f"👤 {name} (總計: ${person_total})"):
                display_cols = group[['item', 'qty', 'subtotal']].rename(columns={'item':'品項', 'qty':'數量', 'subtotal':'小計'})
                st.table(display_cols)
        
        # 3. 全桌總金額
        grand_total = merged_df['subtotal'].sum()
        st.metric("🤑 全桌總金額", f"${grand_total}")