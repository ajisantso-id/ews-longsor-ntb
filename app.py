import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from datetime import datetime
import pytz # <-- Tambahan library buat ngatur zona waktu

# Atur Judul Tab Browser & Bikin Full Layar
st.set_page_config(page_title="Peta Longsor NTB", layout="wide")

# ==========================================
# AMBIL WAKTU REAL-TIME SAAT INI
# ==========================================
# Ambil waktu UTC dan Wita
utc_now = datetime.now(pytz.utc)
wita_now = utc_now.astimezone(pytz.timezone('Asia/Makassar'))

# Format teks persis kayak OFS (Contoh: FRIDAY, 27 FEBRUARY 2026)
tanggal_str = wita_now.strftime("%A, %d %B %Y").upper()
waktu_utc_str = utc_now.strftime("%H:%M:%S UTC")

# ==========================================
# CSS HACK: BIKIN HEADER ALA OFS BMKG & ILANGIN SPACE KOSONG
# ==========================================
st.markdown(f"""
    <style>
        /* 1. Ngilangin Padding Kosong Bawaan Streamlit */
        .block-container {{
            padding-top: 2.5rem !important; /* Sisa dikit buat top bar jam */
            padding-bottom: 0rem !important;
        }}
        header {{visibility: hidden;}} /* Sembunyiin menu default streamlit di atas */
        
        /* 2. Bikin Baris Waktu di Paling Atas (Fixed) */
        .top-time-bar {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            background-color: #ffffff;
            border-bottom: 1px solid #e0e0e0;
            z-index: 99999;
            display: flex;
            justify-content: space-between;
            padding: 6px 30px;
            font-size: 11px;
            color: #0056b3;
            font-weight: bold;
            letter-spacing: 0.5px;
        }}
        
        /* 3. Bikin Header Logo & Judul Rapat */
        .ofs-header {{
            display: flex;
            align-items: center;
            padding: 5px 0px 10px 0px;
        }}
        .ofs-header img {{
            width: 65px;
            margin-right: 15px;
        }}
        .ofs-title h3 {{
            margin: 0;
            padding: 0;
            color: #002B5B; /* Warna Biru BMKG */
            font-size: 20px;
            font-weight: 800;
            line-height: 1.2;
        }}
        .ofs-title p {{
            margin: 0;
            padding: 0;
            color: #444;
            font-size: 15px;
            line-height: 1.2;
        }}
    </style>

    <div class="top-time-bar">
        <div>{tanggal_str}</div>
        <div>STANDAR WAKTU INDONESIA &nbsp;&nbsp;:&nbsp;&nbsp; {waktu_utc_str}</div>
    </div>
    
    <div class="ofs-header">
        <img src="https://www.bmkg.go.id/asset/img/logo/logo-bmkg.png">
        <div class="ofs-title">
            <h3>Stasiun Meteorologi ZAM Lombok</h3>
            <p>Peta Peringatan Dini Longsor NTB</p>
        </div>
    </div>
    
    <hr style="margin: 0; border: none; border-bottom: 2px solid #002B5B;">
""", unsafe_allow_html=True)


# ==========================================
# FUNGSI NARIK DATA DARI MULTIPLE AKUN AWSCENTER
# ==========================================
@st.cache_data(ttl=300) 
def ambil_data_live():
    # --- MASUKIN AKUN AWSCENTER LU DI SINI YA BRO ---
    akun_list = [
        {"username": "97242", "password": "97242@2018"},
        {"username": "97240", "password": "97240@2020"},
    ]

    login_url = "https://awscenter.bmkg.go.id/base/verify"
    api_url = "https://awscenter.bmkg.go.id/dashboard/get_parameter_terkini_hujan"
    kota_ntb = ['Kota Mataram', 'Kab. Lombok Barat', 'Kab. Lombok Tengah', 'Kab. Lombok Timur', 'Kab. Lombok Utara', 'Kab. Sumbawa Barat', 'Kab. Sumbawa', 'Kab. Dompu', 'Kab. Bima', 'Kota Bima']

    semua_data_gabungan = []
    stasiun_tersimpan = set() 

    for akun in akun_list:
        session = requests.Session()
        try:
            respon_login = session.post(login_url, data={"username": akun["username"], "password": akun["password"]})
            if respon_login.status_code == 200:
                respon_data = session.get(api_url)
                data_hujan = respon_data.json()
                for item in data_hujan:
                    if item.get('nama_kota') in kota_ntb:
                        id_alat = item.get('id_station')
                        if id_alat not in stasiun_tersimpan:
                            stasiun_tersimpan.add(id_alat)        
                            semua_data_gabungan.append(item)      
        except Exception as e:
            pass 

    return semua_data_gabungan

# Eksekusi Narik Data Live
data_sensor = ambil_data_live()

# ==========================================
# BAGIAN 1: PETA FULL SCREEN
# ==========================================
# Geser titik tengah ke koordinat antara Lombok & Sumbawa, dan kecilin zoom-nya
m = folium.Map(location=[-8.60, 117.45], zoom_start=8.5)

# MASUKIN ZONA MERAH GEOJSON
try:
    folium.GeoJson(
        "zona_merah.geojson",
        name="Zona Rawan Longsor",
        style_function=lambda feature: {
            'fillColor': '#ff0000',
            'color': '#cc0000',
            'weight': 1,
            'fillOpacity': 0.4,
        }
    ).add_to(m)
except Exception as e:
    pass

# --- TAMBAHIN INI BUAT ZONA MERAH SUMBAWA/BIMA ---
try:
    folium.GeoJson(
        "zona_merah_smb.geojson", # <--- GANTI PAKE NAMA FILE LU
        name="Zona Rawan Longsor Sumbawa dan Bima",
        style_function=lambda feature: {'fillColor': '#ff0000', 'color': '#cc0000', 'weight': 1, 'fillOpacity': 0.4}
    ).add_to(m)
except Exception as e:
    pass

# LOGIKA KATEGORI HUJAN BMKG
for item in data_sensor:
    try:
        lat = float(item['lat'])
        lon = float(item['lng'])
        nama = item['name_station']
        curah_str = str(item['curah']).replace(',', '.')
        curah = float(curah_str) if curah_str.strip() != "" else 0.0

        if curah == 0:
            kategori, potensi, warna, ikon = "Cerah / Berawan", "Aman", "green", "ok-sign"
        elif 0 < curah <= 20:
            kategori, potensi, warna, ikon = "Hujan Ringan", "Aman", "lightgreen", "tint"
        elif 20 < curah <= 50:
            kategori, potensi, warna, ikon = "Hujan Sedang", "Aman", "blue", "cloud"
        elif 50 < curah <= 100:
            kategori, potensi, warna, ikon = "Hujan Lebat", "WASPADA Longsor", "orange", "info-sign"
        elif 100 < curah <= 150:
            kategori, potensi, warna, ikon = "Hujan Sangat Lebat", "SIAGA Longsor", "red", "warning-sign"
        else: 
            kategori, potensi, warna, ikon = "Hujan Ekstrem", "AWAS LONGSOR / BANJIR", "darkred", "flash"

        folium.Marker(
            [lat, lon],
            popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Curah Hujan: <b>{curah} mm</b><br>Kategori: <b>{kategori}</b><br>Potensi: <b>{potensi}</b><br><small>Update: {item['tanggal']} UTC</small></div>",
            tooltip=f"{nama} ({kategori})",
            icon=folium.Icon(color=warna, icon=ikon)
        ).add_to(m)
    except Exception as e:
        continue 

# BIKIN LEGEND MENGAMBANG
legend_html = '''
<div style="
    position: fixed; 
    bottom: 30px; left: 30px; width: 230px; height: auto; 
    background-color: rgba(255, 255, 255, 0.85); 
    border: 2px solid grey; z-index: 9999; 
    font-size: 13px; padding: 10px; border-radius: 8px; 
    box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;
">
    <h4 style="margin-top: 0; margin-bottom: 10px; font-size: 14px; text-align: center; color: black;"><b>Keterangan Peta</b></h4>
    <div style="margin-bottom: 8px;">
        <i style="background: #ff0000; opacity: 0.5; width: 15px; height: 15px; float: left; margin-right: 8px; border: 1px solid #cc0000;"></i>
        <b>Zona Rawan Longsor</b>
    </div>
    <hr style="margin: 5px 0; border-top: 1px solid #ccc;">
    <div style="margin-bottom: 5px; font-size: 11px; color: #333;"><b>Kategori Hujan (24 Jam):</b></div>
    <div style="margin-bottom: 5px;"><i style="background: green; border-radius: 50%; width: 12px; height: 12px; float: left; margin-top: 2px; margin-right: 10px;"></i>Cerah / Ringan (< 20 mm)</div>
    <div style="margin-bottom: 5px;"><i style="background: blue; border-radius: 50%; width: 12px; height: 12px; float: left; margin-top: 2px; margin-right: 10px;"></i>Sedang (20 - 50 mm)</div>
    <div style="margin-bottom: 5px;"><i style="background: orange; border-radius: 50%; width: 12px; height: 12px; float: left; margin-top: 2px; margin-right: 10px;"></i>Lebat / Waspada (50 - 100)</div>
    <div style="margin-bottom: 5px;"><i style="background: red; border-radius: 50%; width: 12px; height: 12px; float: left; margin-top: 2px; margin-right: 10px;"></i>Sangat Lebat / Siaga (100 - 150)</div>
    <div><i style="background: darkred; border-radius: 50%; width: 12px; height: 12px; float: left; margin-top: 2px; margin-right: 10px;"></i>Ekstrem / Awas (> 150 mm)</div>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

st_folium(m, height=650, width="stretch")

st.divider() 

# ==========================================
# BAGIAN 2: TABEL DI BAWAH PETA
# ==========================================
st.subheader("📋 Tabel Detail Monitoring Stasiun")

if data_sensor:
    tabel_data = []
    for item in data_sensor:
        curah_str = str(item['curah']).replace(',', '.')
        curah = float(curah_str) if curah_str.strip() != "" else 0.0

        if curah == 0: kategori_teks, status_teks = 'Cerah/Berawan', '🟢 Aman'
        elif 0 < curah <= 20: kategori_teks, status_teks = 'Hujan Ringan', '🟢 Aman'
        elif 20 < curah <= 50: kategori_teks, status_teks = 'Hujan Sedang', '🔵 Aman'
        elif 50 < curah <= 100: kategori_teks, status_teks = 'Hujan Lebat', '🟠 WASPADA'
        elif 100 < curah <= 150: kategori_teks, status_teks = 'Sangat Lebat', '🔴 SIAGA'
        else: kategori_teks, status_teks = 'Ekstrem', '⚫ AWAS'

        tabel_data.append({
            'Stasiun': item['name_station'],
            'Hujan (mm)': curah,
            'Intensitas': kategori_teks,
            'Status Area': status_teks,
            'Update Terakhir (UTC)': item['tanggal']
        })

    df = pd.DataFrame(tabel_data)
    df = df.sort_values(by='Hujan (mm)', ascending=False) 
    
    st.dataframe(df, width="stretch", hide_index=True)
else:

    st.warning("Data API masih kosong / belum ketarik.")
