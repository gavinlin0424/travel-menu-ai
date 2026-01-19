import streamlit as st
import google.generativeai as genai

st.title("🤖 API 模型診斷工具")

# 1. 讀取 API Key
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("❌ 找不到 API Key，請檢查 Secrets 設定。")
    st.stop()

# 2. 設定
genai.configure(api_key=api_key)

# 3. 列出所有可用模型
st.subheader("正在查詢可用模型清單...")

try:
    available_models = []
    # 呼叫 Google 查詢所有模型
    for m in genai.list_models():
        # 我們只關心能「生成內容」的模型
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
    
    if available_models:
        st.success(f"✅ 連線成功！你的 API Key 可以使用以下 {len(available_models)} 個模型：")
        st.code("\n".join(available_models))
        
        st.info("請查看上方清單，複製其中一個名字（例如 'models/gemini-1.5-flash'），告訴我你有哪一個。")
    else:
        st.warning("⚠️ 連線成功，但沒有發現任何可用模型。這可能是帳號權限問題。")

except Exception as e:
    st.error(f"❌ 連線失敗，錯誤訊息：{e}")
    st.write("建議：請檢查 API Key 是否正確，或 requirements.txt 版本是否過舊。")