import streamlit as st
import pandas as pd
import json
import time
from PIL import Image
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection

# --- 📱 手機版面設定 CSS ---
st.set_page_config(page_title="家族點餐", page_icon="🍱", layout="centered")
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
    html, body, [class*="css"] { font-family: 'Heiti TC', 'Microsoft JhengHei', sans-serif; }
    button[data-baseweb="tab"] { font-size: 16px !important; padding: 10px !important; flex: 1; }
    input[type="number"] { font-size: 18px !important; text-align: center; }
    .stButton > button { width: 100%; border-radius: 8px; font-weight: bold; padding: 10px; }
    
    /* 店家標題樣式 */
    .shop-header {
        background-color: #ffe0b2;
        color: #e65100;
        padding: 8px;
        border-radius: 5px;
        font-weight: bold;
        margin-top: 15px;
        margin-bottom: 5px;
    }
    
    div.dish-card {
        background-color: #f0f2f6;
        padding: 10px 15px;
        border-radius: 10px;
        margin-bottom: 8px;
        border: 1px solid #e0e0e0;
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
        menu_df = conn.read(worksheet="Menu", ttl=0)
        orders_df = conn.read(worksheet="Orders", ttl=0)
        # 確保欄位存在，避免剛改完表頭報錯
        if 'shop' not in menu_df.columns: menu_df['shop'] = '未分類'
        if 'shop' not in orders_df.columns: orders_df['shop'] = '未分類'
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

tab1, tab2, tab3 = st.tabs(["🍽️ 點餐", "📊 統計", "➕ 加店家"])

# =======================
# Tab 1: 點餐 (依店家分類)
# =======================
with tab1:
    if menu_df.empty:
        st.info("目前沒有菜單，請去「➕ 加店家」新增。")
    else:
        # 準備舊訂單 map: key = "店家_菜名" (避免不同店同菜名混淆)
        my_orders = orders_df[orders_df['name'] == st.session_state.user_name]
        my_order_map = {}
        for _, r in my_orders.iterrows():
            key = f"{r['shop']}_{r['item']}"
            my_order_map[key] = r['qty']
        
        current_input = {}
        
        with st.form("order_form"):
            # 取得所有店家清單
            shops = menu_df['shop'].unique()
            
            for shop_name in shops:
                if not shop_name: continue # 跳過空名稱
                
                # 顯示店家標題
                st.markdown(f"<div class='shop-header'>🏪 {shop_name}</div>", unsafe_allow_html=True)
                
                # 篩選該店家的菜
                shop_menu = menu_df[menu_df['shop'] == shop_name]
                
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
            # 清除這個人所有的舊訂單，重新寫入
            clean_orders = orders_df[orders_df['name'] != st.session_state.user_name]
            
            new_rows = []
            for unique_key, qty in current_input.items():
                if qty > 0:
                    # 還原 unique_key 回 shop 和 item
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
        # 合併價格 (需用 shop + item 雙重對應)
        merged = pd.merge(orders_df, menu_df, on=["shop", "item"], how="left")
        merged['subtotal'] = merged['qty'] * merged['price']
        
        total = merged['subtotal'].sum()
        st.metric("💰 總金額", f"${int(total)}")
        
        # 依店家分組統計
        st.subheader("📋 廚房準備清單")
        
        shops_in_order = merged['shop'].unique()
        for shop in shops_in_order:
            st.markdown(f"**🏪 {shop}**")
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
# Tab 3: 加店家 (多店家支援)
# =======================
with tab3:
    st.write("### 📸 新增菜單")
    
    # 1. 先輸入店家名稱
    shop_name_input = st.text_input("🏪 請輸入店家名稱 (例如：50嵐)", placeholder="未輸入會變成「未分類」")
    uploaded_file = st.file_uploader("上傳菜單照片", type=["jpg", "png", "jpeg"])
    
    if uploaded_file and st.button("✨ 開始解析"):
        if not shop_name_input:
            st.error("⚠️ 請先輸入店家名稱！")
        else:
            with st.spinner(f"正在讀取【{shop_name_input}】的菜單..."):
                try:
                    img = Image.open(uploaded_file)
                    model = genai.GenerativeModel(model_name="gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
                    prompt = """
                    識別菜單，輸出JSON list: [{"item": "菜名", "price": 數字}]。
                    非繁體中文請翻譯。無價格填0。
                    """
                    resp = model.generate_content([prompt, img])
                    data = json.loads(resp.text)
                    
                    # 加上店家欄位
                    new_df = pd.DataFrame(data)
                    new_df['shop'] = shop_name_input
                    
                    # 調整欄位順序
                    new_df = new_df[['shop', 'item', 'price']]
                    
                    # 合併並存檔
                    combined = pd.concat([menu_df, new_df], ignore_index=True)
                    # 同一家店、同菜名才去除重複
                    combined = combined.drop_duplicates(subset=['shop', 'item'], keep='last')
                    
                    save_menu(combined)
                    st.success(f"成功新增 {shop_name_input} 的 {len(data)} 道菜！")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"解析失敗: {e}")

    st.write("---")
    st.write("### ✍️ 手動輸入單品")
    with st.form("manual_add"):
        m_shop = st.text_input("店家", value=shop_name_input)
        m_item = st.text_input("菜名")
        m_price = st.number_input("價格", min_value=0)
        
        if st.form_submit_button("新增"):
            if m_shop and m_item:
                row = pd.DataFrame([{"shop": m_shop, "item": m_item, "price": m_price}])
                combined = pd.concat([menu_df, row], ignore_index=True).drop_duplicates(subset=['shop', 'item'])
                save_menu(combined)
                st.success("已新增")
                st.rerun()