import json
import os
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import pytz 
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
import streamlit as st 
import streamlit.components.v1 as components # <--- PENTING BUAT JAM JS!

# ==========================================
# 1. ATUR HALAMAN (WAJIB PALING ATAS!)
# ==========================================
st.set_page_config(
    page_title="Dashboard EWS NTB",
    page_icon="⛈️",
    layout="wide",
    initial_sidebar_state="expanded" 
)

# ==========================================
# 2. CSS SAKTI: HEADER RAPAT & BERSIH
# ==========================================
st.markdown("""
    <style>
    /* A. PEPETIN PETA KE ATAS & FULL KANAN KIRI */
    .main .block-container {
        max-width: 100% !important;
        padding-top: 3.5rem !important; /* Jarak pas buat Header Custom */
        padding-right: 0rem !important;
        padding-left: 0rem !important;
        padding-bottom: 0rem !important;
    }
    
    /* B. HAPUS MENU STREAMLIT DI KANAN ATAS (Deploy dll) */
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    footer {display: none !important;}
    
    /* C. AMANKAN TOMBOL SIDEBAR (Biar Gak Nabrak Header) */
    header[data-testid="stHeader"] { 
        background: transparent !important; 
        z-index: 999999 !important; 
    }

    /* D. BIKIN HEADER PUTIH ALA AWS CENTER DI ATAS PETA */
    .custom-header {
        position: fixed;
        top: 0;
        left: 4rem; /* KITA KASIH RUANG KOSONG DI KIRI BUAT TOMBOL PANAH STREAMLIT! */
        right: 0;
        height: 3.5rem;
        background-color: white;
        z-index: 99999;
        border-bottom: 2px solid #002B5B;
        display: flex;
        align-items: center;
        padding-left: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .custom-header img {
        height: 35px;
        margin-right: 15px;
    }
    .custom-header h3 {
        margin: 0;
        color: #002B5B;
        font-size: 20px;
        font-weight: 800;
        line-height: 1;
    }
    .custom-header span {
        margin-left: 15px;
        color: #555;
        font-size: 15px;
        border-left: 2px solid #ccc;
        padding-left: 15px;
    }

    /* E. NAIKIN PETA DIKIT BIAR SPACE PUTIH HILANG TOTAL */
    iframe[title="streamlit_folium.st_folium"] {
        margin-top: -15px !important;
    }
    </style>
    
    <div class="custom-header">
        <img src="https://www.bmkg.go.id/asset/img/logo/logo-bmkg.png">
        <h3>BMKG</h3>
        <span>Dashboard Peringatan Dini Longsor dan Banjir NTB</span>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. MESIN WAKTU & REFRESH DATA (Tiap 5 Menit)
# ==========================================
st_autorefresh(interval=300000, limit=None, key="auto_refresh_bmkg") 

if 'offset_hari' not in st.session_state:
    st.session_state.offset_hari = 0

def set_hari(offset):
    st.session_state.offset_hari = offset

tanggal_pilih = date.today() - timedelta(days=st.session_state.offset_hari)

# ==========================================
# 4. FUNGSI PENARIKAN DATA
# ==========================================
@st.cache_data(ttl=300) 
def ambil_data_live():
    akun_list = [
        {"username": st.secrets["AWSCENTER_USER"], "password": st.secrets["AWSCENTER_PASS"]},
        {"username": st.secrets["AWSCENTER_USER2"], "password": st.secrets["AWSCENTER_PASS2"]},
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

data_sensor = [] 
if st.session_state.offset_hari == 0:
    with st.spinner("Sedang menarik data Real-Time..."):
        data_sensor = ambil_data_live()
elif st.session_state.offset_hari == 1:
    if os.path.exists('data_h1.json'):
        with open('data_h1.json', 'r') as f: data_sensor = json.load(f)
elif st.session_state.offset_hari == 2:
    if os.path.exists('data_h2.json'):
        with open('data_h2.json', 'r') as f: data_sensor = json.load(f)

# ==========================================
# 5. SIDEBAR (MENU KIRI - AMAN TERKENDALI)
# ==========================================
with st.sidebar:
    # A. Judul Minimalis
    st.image("https://www.bmkg.go.id/asset/img/logo/logo-bmkg.png", width=60)
    st.markdown("<h3 style='margin-top: 5px; margin-bottom: 0px; color:#002B5B;'>Stamet ZAM Lombok</h3>", unsafe_allow_html=True)
    st.divider()

    # B. JAM REALTIME (JAVASCRIPT MURNI!)
    clock_html = """
    <div id="clock_container" style="font-family: sans-serif; color: #333; font-size: 14px; font-weight: bold;">
        Waktu Server (UTC):<br>
        <span id="jam_digital" style="font-size: 17px; color: #002B5B;">Memuat Jam...</span>
    </div>
    <script>
        function updateClock() {
            var d = new Date();
            var days = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'];
            var months = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'];
            
            var dayName = days[d.getUTCDay()];
            var date = ("0" + d.getUTCDate()).slice(-2);
            var monthName = months[d.getUTCMonth()];
            var year = d.getUTCFullYear();
            var h = ("0" + d.getUTCHours()).slice(-2);
            var m = ("0" + d.getUTCMinutes()).slice(-2);
            var s = ("0" + d.getUTCSeconds()).slice(-2);
            
            document.getElementById('jam_digital').innerHTML = dayName + ", " + date + " " + monthName + " " + year + "<br>" + h + ":" + m + ":" + s + " UTC";
        }
        setInterval(updateClock, 1000); // Trigger tiap detik
        updateClock();
    </script>
    """
    components.html(clock_html, height=75) # Bikin Iframe untuk Script
    st.divider()

    # C. Tombol Mesin Waktu
    st.markdown("#### ⏳ Kontrol Data")
    st.button("✅ Data Hari Ini", on_click=set_hari, args=(0,), use_container_width=True)
    st.button("⏪ Data Kemarin (H-1)", on_click=set_hari, args=(1,), use_container_width=True)
    st.button("⏮️ Data Selumbari (H-2)", on_click=set_hari, args=(2,), use_container_width=True) 

    if st.session_state.offset_hari == 0: label = f"Menampilkan: Hari Ini ({tanggal_pilih.strftime('%d %b %Y')})"
    elif st.session_state.offset_hari == 1: label = f"Menampilkan: Kemarin ({tanggal_pilih.strftime('%d %b %Y')})"
    else: label = f"Menampilkan: Selumbari ({tanggal_pilih.strftime('%d %b %Y')})"
    st.info(f"📅 **{label}**")
    st.divider()

    # D. Tabel Full Versi Awal
    st.markdown("#### 📋 Tabel Stasiun")
    if data_sensor:
        tabel_data = []
        for item in data_sensor:
            curah_str = str(item['curah']).replace(',', '.')
            curah = float(curah_str) if curah_str.strip() != "" else 0.0

            if curah == 0: kategori_teks, status_teks = 'Cerah', '🟢 Aman'
            elif 0 < curah <= 20: kategori_teks, status_teks = 'Ringan', '🟢 Aman'
            elif 20 < curah <= 50: kategori_teks, status_teks = 'Sedang', '🔵 Aman'
            elif 50 < curah <= 100: kategori_teks, status_teks = 'Lebat', '🟠 Waspada'
            elif 100 < curah <= 150: kategori_teks, status_teks = 'Sgt Lebat', '🔴 Siaga'
            else: kategori_teks, status_teks = 'Ekstrem', '⚫ Awas'

            tabel_data.append({
                'Stasiun': item['name_station'],
                'Kab/Kota': item['nama_kota'],
                'Hujan': curah,
                'Ket': kategori_teks,
                'Area': status_teks,
                'Update': item['tanggal']
            })

        df = pd.DataFrame(tabel_data).sort_values(by="Hujan", ascending=False)
        styled_df = df.style.set_properties(subset=["Kab/Kota", "Hujan", "Ket", "Area", "Update"], **{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}]).format({"Hujan": "{:.1f}"})
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=450)
    else:
        st.warning("Data API belum ketarik.")

# ==========================================
# 6. PETA UTAMA
# ==========================================
m = folium.Map(location=[-8.65, 117.36], zoom_start=8.5, tiles=None, attributionControl=False)

folium.TileLayer('http://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}', attr=' ', name='Google Maps (Standar)', overlay=False, control=True).add_to(m)
folium.TileLayer('http://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}', attr=' ', name='Google Satellite (Satelit)', overlay=False, control=True, show=False).add_to(m)

def style_kerentanan(feature):
    kategori = str(feature['properties'].get('REMARK', '')).upper()
    if 'SANGAT TINGGI' in kategori: res = {'fillColor': '#cc0000', 'color': '#cc0000', 'weight': 1, 'fillOpacity': 0.6}
    elif 'TINGGI' in kategori: res = {'fillColor': '#ff3385', 'color': '#ff3385', 'weight': 1, 'fillOpacity': 0.6}
    elif 'MENENGAH' in kategori or 'SEDANG' in kategori: res = {'fillColor': '#ffff00', 'color': '#ffff00', 'weight': 1, 'fillOpacity': 0.6}
    elif 'SANGAT RENDAH' in kategori: res = {'fillColor': '#00ccff', 'color': '#00ccff', 'weight': 1, 'fillOpacity': 0.3}
    else: res = {'fillColor': '#00cc00', 'color': '#00cc00', 'weight': 1, 'fillOpacity': 0.3}
    res['interactive'] = False 
    return res

def style_banjir(feature):
    try: tingkat_bahaya = int(float(feature['properties'].get('DN', 0)))
    except: tingkat_bahaya = 0
    warna, opacity = ('#00008B', 0.5) if tingkat_bahaya == 1 else ('#000000', 0.0)
    return {'fillColor': warna, 'color': warna, 'weight': 0.5 if opacity > 0 else 0, 'fillOpacity': opacity, 'interactive': False}

try: folium.GeoJson("zona_merahfix.geojson", name="Zona Kerentanan Gerakan Tanah", style_function=style_kerentanan, show=False).add_to(m)
except: pass
try: folium.GeoJson("banjir_ntb.geojson", name="Zona Rawan Banjir (InaRISK)", style_function=style_banjir, show=False).add_to(m)
except: pass

for item in data_sensor:
    try:
        lat, lon = float(item['lat']), float(item['lng'])
        nama, tanggal = item['name_station'], item.get('tanggal', 'Waktu tidak diketahui')
        curah_raw = item.get('curah', '')
        
        if curah_raw is None or str(curah_raw).strip() == "" or str(curah_raw).lower() == "offline" or float(str(curah_raw).replace(',', '.')) < 0:
            html_offline = '<div style="background: grey; border-radius: 50%; width: 18px; height: 18px; color: red; text-align: center; line-height: 16px; font-weight: bold; border: 2px solid white; box-shadow: 1px 1px 3px rgba(0,0,0,0.5); font-size: 12px;">✖</div>'
            folium.Marker([lat, lon], popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Status: <b>OFFLINE / ERROR</b><br><small>Update: {tanggal} UTC</small></div>", tooltip=f"{nama}: OFFLINE", icon=folium.DivIcon(html=html_offline)).add_to(m)
            continue
            
        curah = float(str(curah_raw).replace(',', '.'))
        if curah < 50:
            if curah == 0: kategori, status_area, fill_warna = "Cerah", "Aman", "blue"
            elif 0 < curah <= 20: kategori, status_area, fill_warna = "Hujan Ringan", "Aman", "green"
            else: kategori, status_area, fill_warna = "Hujan Sedang", "Aman", "#F5DEB3" 
            folium.CircleMarker(location=[lat, lon], radius=6, color='black', weight=1.5, fill_color=fill_warna, fill_opacity=0.9, popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Curah Hujan: <b>{curah} mm</b><br>Kategori: <b>{kategori}</b><br>Status Area: <b>{status_area}</b><br><small>Update: {tanggal} UTC</small></div>", tooltip=f"{nama}: {curah} mm ({kategori})").add_to(m)
        else:
            if 50 <= curah <= 100: kategori, status_area, warna, ikon, warna_ikon = "Hujan Lebat", "WASPADA", "orange", "info-sign", "white"
            elif 100 < curah <= 150: kategori, status_area, warna, ikon, warna_ikon = "Hujan Sangat Lebat", "SIAGA", "red", "warning-sign", "white"
            else: kategori, status_area, warna, ikon, warna_ikon = "Hujan Ekstrem", "AWAS", "darkred", "flash", "white"
            folium.Marker([lat, lon], popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Curah Hujan: <b>{curah} mm</b><br>Kategori: <b>{kategori}</b><br>Status Area: <b>{status_area}</b><br><small>Update: {tanggal} UTC</small></div>", tooltip=f"{nama} ({kategori})", icon=folium.Icon(color=warna, icon=ikon, icon_color=warna_ikon)).add_to(m)
    except Exception as e: continue

# Kotak Legend 
legend_bahaya = '''
<div style="position: fixed; bottom: 350px; right: 15px; width: 220px; height: auto; background-color: rgba(255, 255, 255, 0.9); border: 2px solid grey; z-index: 9999; font-size: 11px; padding: 10px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;">
    <h4 style="margin-top: 0; margin-bottom: 8px; font-size: 13px; text-align: center; color: black;"><b>Kategori Bahaya</b></h4>
    <div style="margin-bottom: 4px;"><b>Kerentanan Gerakan Tanah:</b></div>
    <div style="margin-bottom: 2px;"><i style="background: #cc0000; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Sangat Tinggi</div>
    <div style="margin-bottom: 2px;"><i style="background: #ff3385; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Tinggi</div>
    <div style="margin-bottom: 2px;"><i style="background: #ffff00; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Menengah</div>
    <div style="margin-bottom: 2px;"><i style="background: #00cc00; opacity: 0.3; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Rendah</div>
    <div style="margin-bottom: 6px;"><i style="background: #00ccff; opacity: 0.3; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Sangat Rendah</div>
    <div style="margin-top: 8px;"><strong>Kerentanan Banjir:</strong><br><i style="background:#00008B; width:15px; height:15px; float:left; margin-right:8px; opacity:0.7; border: 1px solid #0000FF;"></i> Rawan Banjir (InaRISK)<br></div>
</div>
'''

legend_peringatan = '''
<div style="position: fixed; bottom: 20px; right: 15px; width: 220px; height: auto; background-color: rgba(255, 255, 255, 0.9); border: 2px solid grey; z-index: 9999; font-size: 11px; padding: 10px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;">
    <h4 style="margin-top: 0; margin-bottom: 8px; font-size: 13px; text-align: center; color: black;"><b>Status Peringatan</b></h4>
    <link rel="stylesheet" href="
