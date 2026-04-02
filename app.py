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

# ==========================================
# 1. ATUR HALAMAN (WAJIB PALING ATAS!)
# ==========================================
st.set_page_config(
    page_title="Dashboard EWS NTB",
    page_icon="⛈️",
    layout="wide",
    initial_sidebar_state="collapsed" # Sengaja default ditutup biar buka web langsung full peta!
)

# ==========================================
# 2. CSS SAKTI: SIDEBAR NGAMBANG & HEADER RAPAT
# ==========================================
st.markdown("""
    <style>
    /* A. PEPETIN PETA KE HEADER (Hilangin Space Putih) */
    .block-container {
        max-width: 100% !important;
        padding-top: 55px !important; /* Pas banget sama tinggi Header AWS */
        padding-right: 0rem !important;
        padding-left: 0rem !important;
        padding-bottom: 0rem !important;
    }
    
    /* B. HILANGIN FITUR STREAMLIT DI POJOK KANAN ATAS */
    [data-testid="stToolbar"] {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    
    /* C. MENGAMANKAN TOMBOL SIDEBAR BIAR BISA DITUTUP */
    header { 
        background: transparent !important; 
        z-index: 999999 !important; /* Harus paling tinggi biar tombol panahnya bisa diklik */
    }
    
    /* D. SIDEBAR MENGAMBANG (OVERLAY) */
    [data-testid="stSidebar"] {
        position: absolute !important;
        z-index: 99999 !important;
        height: 100vh !important;
        background-color: rgba(255, 255, 255, 0.95) !important;
        box-shadow: 2px 0 10px rgba(0,0,0,0.2);
    }

    /* E. BIKIN HEADER PUTIH ALA AWS CENTER */
    .header-aws {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 55px; /* Tinggi disesuaikan */
        background-color: white;
        z-index: 9999; /* Ngumpet di bawah tombol panah sidebar */
        border-bottom: 2px solid #002B5B;
        display: flex;
        align-items: center;
        padding-left: 60px; /* Jarak aman biar tombol panah Streamlit gak ketiban teks */
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    .header-aws img {
        height: 35px;
        margin-right: 15px;
    }
    .header-aws h3 {
        margin: 0;
        color: #002B5B;
        font-size: 20px;
        font-weight: 800;
        line-height: 1;
    }
    .header-aws span {
        margin-left: 15px;
        color: #555;
        font-size: 15px;
        border-left: 2px solid #ccc;
        padding-left: 15px;
    }
    </style>
    
    <div class="header-aws">
        <img src="https://www.bmkg.go.id/asset/img/logo/logo-bmkg.png">
        <h3>BMKG</h3>
        <span>Dashboard Peringatan Dini Longsor dan Banjir NTB</span>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 3. WAKTU REALTIME (Refresh Tiap 1 Menit)
# ==========================================
st_autorefresh(interval=60000, limit=None, key="auto_refresh_bmkg") # 60000 ms = 1 menit

utc_now = datetime.now(pytz.utc)
wita_now = utc_now.astimezone(pytz.timezone('Asia/Makassar'))
tanggal_str = wita_now.strftime("%A, %d %B %Y").upper()
waktu_utc_str = utc_now.strftime("%H:%M:%S UTC")

if 'offset_hari' not in st.session_state:
    st.session_state.offset_hari = 0

def set_hari(offset):
    st.session_state.offset_hari = offset

tanggal_pilih = date.today() - timedelta(days=st.session_state.offset_hari)
tanggal_api = tanggal_pilih.strftime("%Y-%m-%d")

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
        if not data_sensor: st.error("Gagal menarik data Live / Data kosong.")
elif st.session_state.offset_hari == 1:
    if os.path.exists('data_h1.json'):
        with open('data_h1.json', 'r') as f: data_sensor = json.load(f)
    else: st.warning("⚠️ Data histori Kemarin belum tersedia.")
elif st.session_state.offset_hari == 2:
    if os.path.exists('data_h2.json'):
        with open('data_h2.json', 'r') as f: data_sensor = json.load(f)
    else: st.warning("⚠️ Data histori H-2 belum tersedia.")

# ==========================================
# 5. SIDEBAR (MENU KIRI)
# ==========================================
with st.sidebar:
    # 4. Judul Sidebar Simpel
    st.image("https://www.bmkg.go.id/asset/img/logo/logo-bmkg.png", width=60)
    st.markdown("<h3 style='margin-top: 5px; margin-bottom: 0px; color:#002B5B;'>Stamet ZAM Lombok</h3>", unsafe_allow_html=True)
    
    st.markdown(f"**Waktu:** {tanggal_str}<br>*{waktu_utc_str}*", unsafe_allow_html=True)
    st.divider()

    st.markdown("#### ⏳ Kontrol Waktu Data")
    st.button("✅ Data Hari Ini", on_click=set_hari, args=(0,), use_container_width=True)
    st.button("⏪ Data Kemarin (H-1)", on_click=set_hari, args=(1,), use_container_width=True)
    st.button("⏮️ Data Selumbari (H-2)", on_click=set_hari, args=(2,), use_container_width=True) 

    if st.session_state.offset_hari == 0: label = f"Data Hari Ini ({tanggal_pilih.strftime('%d %B %Y')})"
    elif st.session_state.offset_hari == 1: label = f"Data Kemarin ({tanggal_pilih.strftime('%d %B %Y')})"
    else: label = f"Data Selumbari ({tanggal_pilih.strftime('%d %B %Y')})"
    st.info(f"📅 **{label}**")
    st.divider()

    # 6. Tabel Kembali Full
    st.markdown("#### 📋 Detail Monitoring Stasiun")
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
                'Hujan (mm)': curah,
                'Intensitas': kategori_teks,
                'Status Area': status_teks,
                'Update Terakhir (UTC)': item['tanggal']
            })

        df = pd.DataFrame(tabel_data).sort_values(by="Hujan (mm)", ascending=False)
        kolom_center = ["Kab/Kota", "Hujan (mm)", "Intensitas", "Status Area"]
        styled_df = df.style.set_properties(subset=kolom_center, **{'text-align': 'center'}).set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}]).format({"Hujan (mm)": "{:.1f}"})
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=500)
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
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">
    <div style="margin-bottom: 5px; font-weight: bold; color: #333;">Intensitas Hujan (24 Jam):</div>
    <div style="margin-bottom: 6px; height: 18px;"><div style="background: blue; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;"><i class="glyphicon glyphicon-cloud"></i></div><span style="line-height: 18px;">Cerah (0 mm)</span></div>
    <div style="margin-bottom: 6px; height: 18px;"><div style="background: green; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;"><i class="glyphicon glyphicon-tint"></i></div><span style="line-height: 18px;">Ringan (0.1 - 20 mm)</span></div>
    <div style="margin-bottom: 6px; height: 18px;"><div style="background: beige; border-radius: 50%; width: 18px; height: 18px; color: black; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px; border: 1px solid #ccc;"><i class="glyphicon glyphicon-tint"></i></div><span style="line-height: 18px;">Sedang (20 - 50 mm)</span></div>
    <div style="margin-bottom: 6px; height: 18px;"><div style="background: orange; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;"><i class="glyphicon glyphicon-info-sign"></i></div><span style="line-height: 18px;">Lebat (50 - 100 mm)</span> </div>
    <div style="margin-bottom: 6px; height: 18px;"><div style="background: red; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;"><i class="glyphicon glyphicon-warning-sign"></i></div><span style="line-height: 18px;">Sangat Lebat (100-150 mm)</span></div>
    <div style="margin-bottom: 6px; height: 18px;"><div style="background: darkred; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;"><i class="glyphicon glyphicon-flash"></i></div><span style="line-height: 18px;">Ekstrem (> 150 mm)</span></div>
    <hr style="margin: 8px 0; border-top: 1px dashed #999;">
    <div style="margin-bottom: 5px; font-weight: bold; color: #333;">Level Area:</div>
    <div style="margin-bottom: 4px; height: 14px;"><i style="background: orange; opacity: 0.8; width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 2px; margin-top: 1px;"></i><span style="line-height: 14px;">Waspada</span></div>
    <div style="margin-bottom: 4px; height: 14px;"><i style="background: red; opacity: 0.8; width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 2px; margin-top: 1px;"></i><span style="line-height: 14px;">Siaga</span></div>
    <div style="margin-bottom: 0px; height: 14px;"><i style="background: darkred; opacity: 0.8; width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 2px; margin-top: 1px;"></i><span style="line-height: 14px;">Awas</span></div>
</div>
'''

m.get_root().html.add_child(folium.Element(legend_bahaya))
m.get_root().html.add_child(folium.Element(legend_peringatan))
folium.LayerControl().add_to(m)

# TAMPILKAN PETA
st_folium(m, use_container_width=True, height=900, returned_objects=[])

# Download Tombol
nama_file_peta = "Peta_EWS_NTB.html"
m.save(nama_file_peta)
with open(nama_file_peta, "rb") as file:
    st.sidebar.download_button(label="📥 Download Peta (HTML)", data=file, file_name=nama_file_peta, mime="text/html")
