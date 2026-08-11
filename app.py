import streamlit as st
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import os

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Zeynel Oto - Stok Takip", page_icon="🔧", layout="centered")

DB_FILE = "stok_verileri.json"

# --- VERİTABANI YÜKLEME & KAYDETME ---
def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return pd.DataFrame(data)
    else:
        default_data = [
            {"Barkod": "86900001", "Parça Adı": "Ford Focus 1.5 TDCi Yağ Filtresi", "Stok": 12, "Kritik Limit": 3},
            {"Barkod": "86900002", "Parça Adı": "Ford Transit Hava Filtresi", "Stok": 2, "Kritik Limit": 5},
            {"Barkod": "86900003", "Parça Adı": "5W30 Motor Yağı (4L)", "Stok": 8, "Kritik Limit": 4},
        ]
        save_data(pd.DataFrame(default_data))
        return pd.DataFrame(default_data)

def save_data(df):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=4)

if "inventory" not in st.session_state:
    st.session_state.inventory = load_data()

# --- ŞİFRE KONTROLÜ ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🔒 Zeynel Oto Stok Paneli")
        st.subheader("Lütfen Giriş Yapın")
        
        password = st.text_input("Giriş Şifresi:", type="password")
        if st.button("Giriş Yap", use_container_width=True):
            if password == "1234":  # Giriş Şifren
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Hatalı Şifre!")
        return False
    return True

if check_password():
    st.title("🔧 Zeynel Oto Stok Panel")
    
    tab1, tab2, tab3 = st.tabs(["📉 Alim Usta (Hızlı Düş / Elle)", "📄 Fatura Okut", "📦 Tüm Stok & Manuel Düzenle"])

    # ==========================================
    # SEKME 1: ALİM USTA HIZLI STOK DÜŞME
    # ==========================================
    with tab1:
        st.header("⚡ Parça Düş / Güncelle")
        
        parca_listesi = st.session_state.inventory["Parça Adı"].tolist()
        secilen_parca = st.selectbox("🔍 Parça İsmi Seçin veya Yazın:", ["Seçiniz..."] + parca_listesi)

        if secilen_parca != "Seçiniz...":
            df = st.session_state.inventory
            match = df[df["Parça Adı"] == secilen_parca]

            if not match.empty:
                idx = match.index[0]
                item_name = df.loc[idx, "Parça Adı"]
                current_stock = int(df.loc[idx, "Stok"])

                st.warning(f"**Mevcut Stok:** {current_stock} Adet -> **{item_name}**")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔴 -1 Adet Düş", use_container_width=True):
                        if current_stock > 0:
                            st.session_state.inventory.loc[idx, "Stok"] -= 1
                            save_data(st.session_state.inventory)
                            st.success(f"1 Adet {item_name} düşüldü!")
                            st.rerun()
                        else:
                            st.error("Stokta kalmadı!")
                with col2:
                    if st.button("🟢 +1 Adet Ekle", use_container_width=True):
                        st.session_state.inventory.loc[idx, "Stok"] += 1
                        save_data(st.session_state.inventory)
                        st.success(f"1 Adet {item_name} eklendi!")
                        st.rerun()

                plaka = st.text_input("Araç Plakası (Opsiyonel):", placeholder="01 ABC 123")

    # ==========================================
    # SEKME 2: PARÇACI FATURASINI FOTOĞRAFLA YÜKLE
    # ==========================================
    with tab2:
        st.header("📸 Faturadan Otomatik Stok Ekle")
        api_key = st.text_input("Gemini API Key:", type="password")
        uploaded_file = st.file_uploader("Fatura Fotoğrafı Yükle / Çek", type=["jpg", "jpeg", "png"])

        if uploaded_file and api_key:
            image = Image.open(uploaded_file)
            st.image(image, caption="Yüklenen Fatura", use_column_width=True)

            if st.button("⚡ Faturayı Çözümle ve Stoğa İşle", use_container_width=True):
                with st.spinner("Yapay zeka faturadaki parçaları okuyor..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        prompt = """
                        Bu faturadaki yedek parçaları ve adetlerini tespit et.
                        SADECE şu JSON formatında cevap ver:
                        [
                          {"parca_adi": "Ürün Adı", "adet": 5, "barkod": "otomatik_kod"}
                        ]
                        """
                        
                        response = model.generate_content([prompt, image])
                        clean_json = response.text.replace("```json", "").replace("```", "").strip()
                        items = json.loads(clean_json)

                        for item in items:
                            new_row = {
                                "Barkod": item.get("barkod", f"AUTO_{len(st.session_state.inventory)+1}"),
                                "Parça Adı": item["parca_adi"],
                                "Stok": int(item["adet"]),
                                "Kritik Limit": 3
                            }
                            st.session_state.inventory = pd.concat([st.session_state.inventory, pd.DataFrame([new_row])], ignore_index=True)
                        
                        save_data(st.session_state.inventory)
                        st.success("Faturadaki parçalar stoğa eklendi!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fatura okuma hatası: {e}")

    # ==========================================
    # SEKME 3: TÜM STOK VE MANUEL DÜZENLEME
    # ==========================================
    with tab3:
        st.header("📦 Depo Durumu & Elle Parça Ekle/Düzenle")
        
        df = st.session_state.inventory
        kritikler = df[df["Stok"] <= df["Kritik Limit"]]
        if not kritikler.empty:
            st.error("⚠️ **AZALAN PARÇALAR (Sipariş Verilmeli):**")
            for _, r in kritikler.iterrows():
                st.write(f"- **{r['Parça Adı']}**: Kalan **{r['Stok']}** adet")
            st.divider()

        with st.expander("➕ Sıfırdan Yeni Parça Ekle (Elle)"):
            y_barkod = st.text_input("Barkod (İsteğe Bağlı):", placeholder="869...")
            y_adi = st.text_input("Parça Adı:", placeholder="Örn: Ford Focus Ön Fren Balatası")
            y_stok = st.number_input("Başlangıç Stoğu:", min_value=1, value=5)
            y_kritik = st.number_input("Kritik Stok Limiti:", min_value=1, value=2)
            
            if st.button("Kaydet ve Stoğa Ekle"):
                if y_adi:
                    yeni_satir = {
                        "Barkod": y_barkod if y_barkod else f"MAN_{len(st.session_state.inventory)+1}",
                        "Parça Adı": y_adi,
                        "Stok": int(y_stok),
                        "Kritik Limit": int(y_kritik)
                    }
                    st.session_state.inventory = pd.concat([st.session_state.inventory, pd.DataFrame([yeni_satir])], ignore_index=True)
                    save_data(st.session_state.inventory)
                    st.success(f"{y_adi} başarıyla eklendi!")
                    st.rerun()
                else:
                    st.error("Lütfen parça adını girin!")

        st.subheader("Mevcut Stok Listesi")
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 Değişiklikleri Kaydet", use_container_width=True):
            st.session_state.inventory = edited_df
            save_data(edited_df)
            st.success("Stok tablosu kaydedildi!")
            st.rerun()
            
        st.divider()
        if st.button("🚪 Çıkış Yap"):
            st.session_state["authenticated"] = False
            st.rerun()
