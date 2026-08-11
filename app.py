import io
import json
import os
from datetime import date, datetime

import google.generativeai as genai
import pandas as pd
from PIL import Image
import streamlit as st

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Zeynel Oto - Profesyonel Stok & Geçmiş Paneli",
    page_icon="🔧",
    layout="wide",
)

DB_FILE = "stok_verileri.json"
HISTORY_FILE = "islem_gecmisi.json"

# --- VERİTABANI İŞLEMLERİ ---
def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return pd.DataFrame(json.load(f))
    else:
        default_data = [
            {
                "Barkod": "86900001",
                "Parça Adı": "Ford Focus 1.5 TDCi Yağ Filtresi",
                "Stok": 12,
                "Kritik Limit": 3,
            },
            {
                "Barkod": "86900002",
                "Parça Adı": "Ford Transit Hava Filtresi",
                "Stok": 2,
                "Kritik Limit": 5,
            },
            {
                "Barkod": "86900003",
                "Parça Adı": "5W30 Motor Yağı (4L)",
                "Stok": 8,
                "Kritik Limit": 4,
            },
        ]
        save_data(pd.DataFrame(default_data))
        return pd.DataFrame(default_data)

def save_data(df):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=4)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            df_h = pd.DataFrame(json.load(f))
            if not df_h.empty and "Tarih_DT" not in df_h.columns:
                df_h["Tarih_DT"] = pd.to_datetime(df_h["Tarih"])
            return df_h
    else:
        return pd.DataFrame(
            columns=[
                "Tarih",
                "İşlem",
                "Parça Adı",
                "Miktar",
                "Plaka",
                "Kalan Stok",
            ]
        )

def add_history(islem_tipi, parca_adi, miktar, plaka, kalan_stok):
    df_h = load_history()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    yeni_kayit = {
        "Tarih": now_str,
        "İşlem": islem_tipi,
        "Parça Adı": parca_adi,
        "Miktar": miktar,
        "Plaka": plaka.strip().upper() if plaka else "BİLİNMİYOR",
        "Kalan Stok": kalan_stok,
    }

    if "Tarih_DT" in df_h.columns:
        df_h = df_h.drop(columns=["Tarih_DT"])

    df_h = pd.concat([pd.DataFrame([yeni_kayit]), df_h], ignore_index=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(df_h.to_dict(orient="records"), f, ensure_ascii=False, indent=4)

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
            if password == "1234":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Hatalı Şifre!")
        return False
    return True

if check_password():
    st.title("🔧 Zeynel Oto Ford Özel Servis - Stok & Hareket Takibi")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📉 Alim Usta (Hızlı Düş / Ekle)",
        "📅 Araç Geçmişi ve İşlem Logları",
        "📦 Tüm Stok & Excel İndir",
        "📄 Fatura Okut (AI)",
    ])

    # ==========================================
    # SEKME 1: ALİM USTA HIZLI STOK DÜŞME
    # ==========================================
    with tab1:
        st.header("⚡ Hızlı Stok Hareketleri")

        arama_metni = st.text_input(
            "🔍 Parça Ara (İsim veya Barkod Yazın):",
            placeholder="Örn: Z Rot, Balata, Filtre...",
        )

        df = st.session_state.inventory
        if arama_metni:
            filtreli_df = df[
                df["Parça Adı"].str.contains(arama_metni, case=False, na=False)
                | df["Barkod"].str.contains(arama_metni, case=False, na=False)
            ]
            parca_listesi = filtreli_df["Parça Adı"].tolist()
        else:
            parca_listesi = df["Parça Adı"].tolist()

        secilen_parca = st.selectbox(
            "📌 Listeden Parçayı Seçin:", ["Seçiniz..."] + parca_listesi
        )

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            islem_adedi = st.number_input(
                "🔢 İşlem Adedi (Kaç Tane?):", min_value=1, value=1, step=1
            )
        with col_p2:
            plaka_input = st.text_input(
                "🚘 Araç Plakası (Zorunlu Değil):", placeholder="Örn: 01 ABC 123"
            ).upper()

        if secilen_parca != "Seçiniz...":
            match = df[df["Parça Adı"] == secilen_parca]

            if not match.empty:
                idx = match.index[0]
                item_name = df.loc[idx, "Parça Adı"]
                current_stock = int(df.loc[idx, "Stok"])

                st.info(
                    f"📌 **Seçilen Ürün:** {item_name} | **Mevcut Depo Stok:**"
                    f" {current_stock} Adet"
                )

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(
                        f"🔴 {islem_adedi} Adet Düş (Araca Takıldı)",
                        use_container_width=True,
                    ):
                        if current_stock >= islem_adedi:
                            st.session_state.inventory.loc[idx, "Stok"] -= islem_adedi
                            yeni_stok = int(st.session_state.inventory.loc[idx, "Stok"])
                            save_data(st.session_state.inventory)
                            add_history(
                                "Stok Düşüldü", item_name, -islem_adedi, plaka_input, yeni_stok
                            )
                            st.success(
                                f"{islem_adedi} Adet {item_name} düşüldü! Kalan Stok:"
                                f" {yeni_stok}"
                            )
                            st.rerun()
                        else:
                            st.error(
                                f"Depoda yeterli stok yok! Mevcut Stok: {current_stock}"
                            )
                with col2:
                    if st.button(
                        f"🟢 {islem_adedi} Adet Ekle (Rafa Koyuldu)",
                        use_container_width=True,
                    ):
                        st.session_state.inventory.loc[idx, "Stok"] += islem_adedi
                        yeni_stok = int(st.session_state.inventory.loc[idx, "Stok"])
                        save_data(st.session_state.inventory)
                        add_history(
                            "Stok Eklendi", item_name, +islem_adedi, plaka_input, yeni_stok
                        )
                        st.success(
                            f"{islem_adedi} Adet {item_name} eklendi! Yeni Stok:"
                            f" {yeni_stok}"
                        )
                        st.rerun()

    # ==========================================
    # SEKME 2: ARAÇ GEÇMİŞİ VE İŞLEM LOGLARI
    # ==========================================
    with tab2:
        st.header("📅 Araç Geçmişi ve İşlem Logları")

        df_history = load_history()

        if not df_history.empty:
            df_history["Tarih_DT"] = pd.to_datetime(df_history["Tarih"])

            # Filtre Paneli
            col_f1, col_f2, col_f3 = st.columns([2, 2, 3])

            with col_f1:
                bas_tarih = st.date_input(
                    "📅 Başlangıç Tarihi:", value=date.today().replace(day=1)
                )
            with col_f2:
                bit_tarih = st.date_input("📅 Bitiş Tarihi:", value=date.today())
            with col_f3:
                filtre_parca = st.text_input(
                    "🔍 Parça Adı Filtresi (İsteğe Bağlı):",
                    placeholder="Örn: Z Rot, Balata, Transit...",
                )

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                filtre_plaka = st.text_input(
                    "🚘 Plaka Sorgu (İsteğe Bağlı):", placeholder="Örn: 01 ABC 123"
                ).upper()

            # Tarih Süzme
            mask = (df_history["Tarih_DT"].dt.date >= bas_tarih) & (
                df_history["Tarih_DT"].dt.date <= bit_tarih
            )
            süzülmüs_df = df_history[mask].copy()

            # Parça İsmi Süzme
            if filtre_parca:
                süzülmüs_df = süzülmüs_df[
                    süzülmüs_df["Parça Adı"].str.contains(
                        filtre_parca, case=False, na=False
                    )
                ]

            # Plaka Süzme
            if filtre_plaka:
                süzülmüs_df = süzülmüs_df[
                    süzülmüs_df["Plaka"].str.contains(
                        filtre_plaka, case=False, na=False
                    )
                ]

            st.divider()

            # Özet Kartları
            if not süzülmüs_df.empty:
                giren = süzülmüs_df[süzülmüs_df["Miktar"] > 0]["Miktar"].sum()
                cikan = abs(süzülmüs_df[süzülmüs_df["Miktar"] < 0]["Miktar"].sum())
                net = giren - cikan

                m1, m2, m3 = st.columns(3)
                m1.metric("🟢 Toplam Giren (Stok)", f"+{giren} Adet")
                m2.metric("🔴 Toplam Çıkan (Araca Takılan)", f"-{cikan} Adet")
                m3.metric("📊 Net Değişim", f"{net} Adet")

                st.subheader("📋 Detaylı Hareket Tablosu")
                gosterilecek_df = süzülmüs_df[[
                    "Tarih",
                    "İşlem",
                    "Parça Adı",
                    "Miktar",
                    "Plaka",
                    "Kalan Stok",
                ]]
                st.dataframe(gosterilecek_df, use_container_width=True)
            else:
                st.warning(
                    "Seçilen tarih aralığında ve kriterlerde bir hareket bulunamadı."
                )
        else:
            st.info("Henüz sistemde kaydedilmiş bir hareket yok.")

    # ==========================================
    # SEKME 3: TÜM STOK & EXCEL İNDİRME
    # ==========================================
    with tab3:
        st.header("📦 Depo Durumu & Manuel Düzenleme")

        df = st.session_state.inventory
        kritikler = df[df["Stok"] <= df["Kritik Limit"]]

        if not kritikler.empty:
            st.error(
                "⚠️ **KRİTİK SEVİYEDEKİ PARÇALAR (EKSİKLER / SİPARİŞ EDİLECEKLER):**"
            )
            st.dataframe(
                kritikler[["Barkod", "Parça Adı", "Stok", "Kritik Limit"]],
                use_container_width=True,
            )
            st.divider()

        # EXCEL RAPORU OLUŞTURMA
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Tüm Stok", index=False)
            if not kritikler.empty:
                kritikler.to_excel(
                    writer, sheet_name="Sipariş Edilecekler (Kritik)", index=False
                )
            else:
                pd.DataFrame([{"Bilgi": "Kritik seviyede ürün yok"}]).to_excel(
                    writer, sheet_name="Sipariş Edilecekler (Kritik)", index=False
                )

        excel_data = buffer.getvalue()

        st.download_button(
            label="📊 TÜM STOK VE KRİTİK LİSTEYİ EXCEL OLARAK İNDİR",
            data=excel_data,
            file_name=(
                f"Zeynel_Oto_Stok_Raporu_{datetime.now().strftime('%d_%m_%Y')}.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            use_container_width=True,
        )
        st.divider()

        with st.expander("➕ Sıfırdan Yeni Parça Tanımla (Elle)"):
            with st.form("yeni_parca_formu", clear_on_submit=True):
                y_barkod = st.text_input("Barkod (İsteğe Bağlı):", placeholder="869...")
                y_adi = st.text_input(
                    "Parça Adı:", placeholder="Örn: Ford Focus Ön Fren Balatası"
                )
                y_stok = st.number_input("Başlangıç Stoğu:", min_value=1, value=5)
                y_kritik = st.number_input(
                    "Kritik Stok Limiti:", min_value=1, value=2
                )

                submitted = st.form_submit_button(
                    "Kaydet ve Stoğa Ekle", use_container_width=True
                )
                if submitted:
                    if y_adi:
                        yeni_satir = {
                            "Barkod": (
                                y_barkod
                                if y_barkod
                                else f"MAN_{len(st.session_state.inventory)+1}"
                            ),
                            "Parça Adı": y_adi,
                            "Stok": int(y_stok),
                            "Kritik Limit": int(y_kritik),
                        }
                        st.session_state.inventory = pd.concat(
                            [st.session_state.inventory, pd.DataFrame([yeni_satir])],
                            ignore_index=True,
                        )
                        save_data(st.session_state.inventory)
                        add_history(
                            "Yeni Parça Tanımlandı",
                            y_adi,
                            int(y_stok),
                            "SİSTEM",
                            int(y_stok),
                        )
                        st.success(f"'{y_adi}' başarıyla stoğa eklendi!")
                        st.rerun()
                    else:
                        st.error("Lütfen parça adını girin!")

        st.subheader("Mevcut Stok Tablosu")
        edited_df = st.data_editor(
            st.session_state.inventory,
            num_rows="dynamic",
            use_container_width=True,
            key="editor",
        )

        if st.button(
            "💾 Değişiklikleri / Silinenleri Kaydet", use_container_width=True
        ):
            st.session_state.inventory = edited_df
            save_data(edited_df)
            st.success("Stok tablosu güncellendi ve kaydedildi!")
            st.rerun()

    # ==========================================
    # SEKME 4: PARÇACI FATURASINI FOTOĞRAFLA YÜKLE
    # ==========================================
    with tab4:
        st.header("📸 Faturadan Otomatik Stok Ekle")
        api_key = st.text_input("Gemini API Key:", type="password")
        uploaded_file = st.file_uploader(
            "Fatura Fotoğrafı Yükle / Çek", type=["jpg", "jpeg", "png"]
        )

        if uploaded_file and api_key:
            image = Image.open(uploaded_file)
            st.image(image, caption="Yüklenen Fatura", use_column_width=True)

            if st.button(
                "⚡ Faturayı Çözümle ve Stoğa İşle", use_container_width=True
            ):
                with st.spinner("Yapay zeka faturadaki parçaları okuyor..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel("gemini-1.5-flash")

                        prompt = """
                        Bu faturadaki yedek parçaları ve adetlerini tespit et.
                        SADECE şu JSON formatında cevap ver:
                        [
                          {"parca_adi": "Ürün Adı", "adet": 5, "barkod": "otomatik_kod"}
                        ]
                        """

                        response = model.generate_content([prompt, image])
                        clean_json = (
                            response.text.replace("```json", "")
                            .replace("```", "")
                            .strip()
                        )
                        items = json.loads(clean_json)

                        for item in items:
                            new_row = {
                                "Barkod": item.get(
                                    "barkod", f"AUTO_{len(st.session_state.inventory)+1}"
                                ),
                                "Parça Adı": item["parca_adi"],
                                "Stok": int(item["adet"]),
                                "Kritik Limit": 3,
                            }
                            st.session_state.inventory = pd.concat(
                                [st.session_state.inventory, pd.DataFrame([new_row])],
                                ignore_index=True,
                            )
                            add_history(
                                "Fatura İle Eklendi",
                                item["parca_adi"],
                                int(item["adet"]),
                                "FATURA",
                                int(item["adet"]),
                            )

                        save_data(st.session_state.inventory)
                        st.success("Faturadaki parçalar stoğa eklendi!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fatura okuma hatası: {e}")

    st.divider()
    if st.button("🚪 Çıkış Yap"):
        st.session_state["authenticated"] = False
        st.rerun()
