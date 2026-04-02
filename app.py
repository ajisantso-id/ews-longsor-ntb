import json
import os
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from datetime import datetime
from datetime import date, timedelta
import pytz # <-- Tambahan library buat ngatur zona waktu
from streamlit_autorefresh import st_autorefresh

# Atur Judul Tab Browser & Bikin Full Layar
st.set_page_config(page_title="Dashboard Peringatan Dini Longsor dan Banjir NTB", layout="wide")

# ==========================================
# FITUR AUTO-REFRESH MODE TV DISPLAY
# ==========================================F
# Refresh halaman secara halus setiap 5 menit (300.000 milidetik)
st_autorefresh(interval=300000, limit=None, key="auto_refresh_bmkg")

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
            padding-top: 0.5rem !important; /* Sisa dikit buat top bar jam */
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
            <p>Dashboard Peringatan Dini Longsor dan Banjir NTB</p>
        </div>
    </div>
    
    <hr style="margin: 0; border: none; border-bottom: 2px solid #002B5B;">
""", unsafe_allow_html=True)

# ==========================================
# 1. OTAK MESIN WAKTU (Taruh di atas sebelum narik data)
# ==========================================

# Pastiin ini ada di atas
if 'offset_hari' not in st.session_state:
    st.session_state.offset_hari = 0

# Fungsi baru, 1 fungsi buat semua tombol!
def set_hari(offset):
    st.session_state.offset_hari = offset

# Hitung tanggalnya di atas, biar data API dan Peta bisa langsung pake
tanggal_pilih = date.today() - timedelta(days=st.session_state.offset_hari)
tanggal_api = tanggal_pilih.strftime("%Y-%m-%d")

# ==========================================
# FUNGSI NARIK DATA DARI MULTIPLE AKUN AWSCENTER
# ==========================================
@st.cache_data(ttl=300) 
def ambil_data_live():
    # --- MASUKIN AKUN AWSCENTER LU DI SINI YA BRO ---
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

# Eksekusi Narik Data Live
#data_sensor = ambil_data_live()

# LOGIKA PINTAR PENARIKAN DATA (LIVE vs HISTORI)
# ==========================================
data_sensor = [] # Kita siapin wadah kosong dulu

# Cek tombol mesin waktu lagi ada di posisi mana
if st.session_state.offset_hari == 0:
    # --- JALUR HARI INI (Tarik Live via API) ---
    with st.spinner("Sedang menarik data Real-Time dari AWS Center..."):
        data_sensor = ambil_data_live()
        if not data_sensor:
            st.error("Gagal menarik data Live / Data kosong.")

elif st.session_state.offset_hari == 1:
    # --- JALUR KEMARIN (H-1) ---
    if os.path.exists('data_h1.json'):
        with open('data_h1.json', 'r') as f:
            data_sensor = json.load(f)
    else:
        st.warning("⚠️ Data histori Kemarin belum tersedia. Robot GitHub belum narik datanya semalam.")

elif st.session_state.offset_hari == 2:
    # --- JALUR SELUMBARI (H-2) ---
    if os.path.exists('data_h2.json'):
        with open('data_h2.json', 'r') as f:
            data_sensor = json.load(f)
    else:
        st.warning("⚠️ Data histori H-2 belum tersedia.")

# ==========================================
# 1. BIKIN PETA KOSONG (HAPUS BASEMAP BAWAAN)
# ==========================================
# Ganti koordinat & zoom sesuai titik tengah NTB lu
m = folium.Map(location=[-8.65, 117.36], zoom_start=8.5, tiles=None, attributionControl=False)

# ==========================================
# 2. PILIHAN BASEMAP 1: GOOGLE MAPS (JALAN) - Default
# ==========================================
folium.TileLayer(
    tiles='http://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}',
    attr=' ',
    name='Google Maps (Standar)',
    overlay=False,
    control=True
).add_to(m)

# ==========================================
# 3. PILIHAN BASEMAP 2: GOOGLE SATELLITE HYBRID
# ==========================================
folium.TileLayer(
    # Perhatiin kodenya 'lyrs=y' (Artinya Hybrid: Satelit + Label Nama Tempat)
    tiles='http://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}',
    attr=' ',
    name='Google Satellite (Satelit)',
    overlay=False,
    control=True,
    show=False
).add_to(m)
# ==========================================
# 5. LAPISAN TENGAH-ATAS: BATAS KEKUASAAN ARG (THIESSEN)
# ==========================================
#try:
 #   folium.GeoJson(
  #      "batas_arg.geojson",
   #     name="Wilayah Cakupan ARG",
    #    style_function=lambda x: {
     #       'color': 'black',       # Warna garis batas hitam
      #      'weight': 1.5,          # Ketebalan garis
       #     'dashArray': '5, 5',    # Bikin garisnya putus-putus biar estetik
        #    'fillOpacity': 0        # Bolongin area dalamnya biar warna PVMBG tetep kelihatan
      #  }
    #).add_to(m)
#except Exception as e:
 #   pass


# ==========================================
# FUNGSI WARNA ZONA RAWAN LONGSOR (PVMBG)
# ==========================================
def style_kerentanan(feature):
    kategori = str(feature['properties'].get('REMARK', '')).upper()
    
    if 'SANGAT TINGGI' in kategori:
        res = {'fillColor': '#cc0000', 'color': '#cc0000', 'weight': 1, 'fillOpacity': 0.6}
    elif 'TINGGI' in kategori:
        res = {'fillColor': '#ff3385', 'color': '#ff3385', 'weight': 1, 'fillOpacity': 0.6}
    elif 'MENENGAH' in kategori or 'SEDANG' in kategori:
        res = {'fillColor': '#ffff00', 'color': '#ffff00', 'weight': 1, 'fillOpacity': 0.6}
    elif 'SANGAT RENDAH' in kategori:
        res = {'fillColor': '#00ccff', 'color': '#00ccff', 'weight': 1, 'fillOpacity': 0.3}
    else:
        res = {'fillColor': '#00cc00', 'color': '#00cc00', 'weight': 1, 'fillOpacity': 0.3}
    
    # TAMBAHKAN JURUS GHOSTING BIAR BISA DI-KLIK TEMBUS KE BAWAH
    res['interactive'] = False 
    return res

# ==========================================
# FUNGSI WARNA ZONA RAWAN BANJIR (INARISK BINARY)
# ==========================================
def style_banjir(feature):
    try:
        tingkat_bahaya = int(float(feature['properties'].get('DN', 0)))
    except:
        tingkat_bahaya = 0
        
    if tingkat_bahaya == 1:
        warna = '#00008B'
        opacity = 0.5
    else:
        warna = '#000000'
        opacity = 0.0 
        
    return {
        'fillColor': warna, 
        'color': warna, 
        'weight': 0.5 if opacity > 0 else 0, 
        'fillOpacity': opacity,
        'interactive': False  # <--- JANGAN LUPA MANTRA INI DI SINI JUGA!
    }
# ==========================================
# LAPISAN TAMBAHAN: ZONA RAWAN LONGSOR (GEOJSON)
# ==========================================
try:
    folium.GeoJson(
        "zona_merahfix.geojson",
        name="Zona Kerentanan Gerakan Tanah",
        style_function=style_kerentanan,
        show=False
    ).add_to(m)
except Exception as e:
    pass

# ==========================================
# 4. LAPISAN TAMBAHAN: ZONA RAWAN BANJIR 
# ==========================================
try:
    folium.GeoJson(
        "banjir_ntb.geojson",
        name="Zona Rawan Banjir (InaRISK)",
        style_function=style_banjir,  # <--- Panggil nama fungsi yang baru kita bikin di sini!
        show=False
    ).add_to(m)
except Exception as e:
    pass
    
# LOGIKA KATEGORI HUJAN & STATUS AREA BMKG
# ==========================================
# PEMBUATAN PIN SENSOR (DINAMIS & DECLUTTERING)
# ==========================================
for item in data_sensor:
    try:
        lat = float(item['lat'])
        lon = float(item['lng'])
        nama = item['name_station']
        tanggal = item.get('tanggal', 'Waktu tidak diketahui')
        
        # 1. CEK KONDISI OFFLINE DULU
        # Kalau datanya kosong (None/"") atau ada tulisan offline
        curah_raw = item.get('curah', '')
        if curah_raw is None or str(curah_raw).strip() == "" or str(curah_raw).lower() == "offline":
            html_offline = '''
            <div style="background: grey; border-radius: 50%; width: 18px; height: 18px; color: red; text-align: center; line-height: 16px; font-weight: bold; border: 2px solid white; box-shadow: 1px 1px 3px rgba(0,0,0,0.5); font-size: 12px;">
                ✖
            </div>
            '''
            folium.Marker(
                [lat, lon],
                popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Status: <b>OFFLINE / NO DATA</b><br><small>Update: {tanggal} UTC</small></div>",
                tooltip=f"{nama}: OFFLINE",
                icon=folium.DivIcon(html=html_offline)
            ).add_to(m)
            continue # Skip ke bawahnya, lanjut ke stasiun berikutnya
            
        # Kalau data hujannya ada, kita ubah jadi angka
        curah_str = str(curah_raw).replace(',', '.')
        curah = float(curah_str)

        # Kadang alat rusak ngirim data -999, kita anggap offline juga
        if curah < 0:
            html_offline = '''
            <div style="background: grey; border-radius: 50%; width: 18px; height: 18px; color: red; text-align: center; line-height: 16px; font-weight: bold; border: 2px solid white; box-shadow: 1px 1px 3px rgba(0,0,0,0.5); font-size: 12px;">
                ✖
            </div>
            '''
            folium.Marker(
                [lat, lon],
                popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Status: <b>ERROR / OFFLINE</b><br><small>Update: {tanggal} UTC</small></div>",
                tooltip=f"{nama}: ERROR",
                icon=folium.DivIcon(html=html_offline)
            ).add_to(m)
            continue

        # ==========================================
        # 2. KONDISI AMAN (< 50 mm) -> JADI TITIK KECIL
        # ==========================================
        if curah < 50:
            if curah == 0:
                kategori, status_area, fill_warna = "Cerah / Berawan", "Aman", "blue"
            elif 0 < curah <= 20:
                kategori, status_area, fill_warna = "Hujan Ringan", "Aman", "green"
            else:
                kategori, status_area, fill_warna = "Hujan Sedang", "Aman", "#F5DEB3" # Kode warna Beige (Kuning Gandum)

            folium.CircleMarker(
                location=[lat, lon],
                radius=6, # Ukuran titiknya
                color='black', # Garis tepi hitam biar titiknya kontras
                weight=1.5,
                fill_color=fill_warna,
                fill_opacity=0.9,
                popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Curah Hujan: <b>{curah} mm</b><br>Kategori: <b>{kategori}</b><br>Status Area: <b>{status_area}</b><br><small>Update: {tanggal} UTC</small></div>",
                tooltip=f"{nama}: {curah} mm ({kategori})"
            ).add_to(m)

        # ==========================================
        # 3. KONDISI BAHAYA (>= 50 mm) -> MUNCUL PIN GEDE!
        # ==========================================
        else:
            if 50 <= curah <= 100:
                kategori, status_area, warna, ikon, warna_ikon = "Hujan Lebat", "WASPADA", "orange", "info-sign", "white"
            elif 100 < curah <= 150:
                kategori, status_area, warna, ikon, warna_ikon = "Hujan Sangat Lebat", "SIAGA", "red", "warning-sign", "white"
            else:
                kategori, status_area, warna, ikon, warna_ikon = "Hujan Ekstrem", "AWAS", "darkred", "flash", "white"
            
            # Kita pakai folium.Marker bawaan punya lu buat nampilin icon gedenya
            folium.Marker(
                [lat, lon],
                popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Curah Hujan: <b>{curah} mm</b><br>Kategori: <b>{kategori}</b><br>Status Area: <b>{status_area}</b><br><small>Update: {tanggal} UTC</small></div>",
                tooltip=f"{nama} ({kategori})",
                icon=folium.Icon(color=warna, icon=ikon, icon_color=warna_ikon)
            ).add_to(m)

    except Exception as e:
        continue
        # ==========================================
# BIKIN LEGEND MENGAMBANG (UPDATE STANDAR PVMBG + BATAS ARG)

# ==========================================
# 1. KOTAK LEGEND BAHAYA (Posisi Atas)
# ==========================================
legend_bahaya = '''
<div style="
    position: fixed; 
    bottom: 350px; left: 30px; width: 230px; height: auto; 
    background-color: rgba(255, 255, 255, 0.9); 
    border: 2px solid grey; z-index: 9999; 
    font-size: 12px; padding: 10px; border-radius: 8px; 
    box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;
">
    <h4 style="margin-top: 0; margin-bottom: 10px; font-size: 14px; text-align: center; color: black;"><b>Kategori Bahaya</b></h4>
    
    <div style="margin-bottom: 5px;"><b>Kerentanan Gerakan Tanah (PVMBG):</b></div>
    <div style="margin-bottom: 2px;"><i style="background: #cc0000; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Sangat Tinggi</div>
    <div style="margin-bottom: 2px;"><i style="background: #ff3385; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Tinggi</div>
    <div style="margin-bottom: 2px;"><i style="background: #ffff00; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Menengah</div>
    <div style="margin-bottom: 2px;"><i style="background: #00cc00; opacity: 0.3; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Rendah</div>
    <div style="margin-bottom: 6px;"><i style="background: #00ccff; opacity: 0.3; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Sangat Rendah</div>
    
    <div style="margin-top: 8px;">
        <strong>Kerentanan Banjir:</strong><br>
        <i style="background:#00008B; width:15px; height:15px; float:left; margin-right:8px; opacity:0.7; border: 1px solid #0000FF;"></i> Rawan Banjir (InaRISK)<br>
    </div>

    <div style="margin-top: 8px; margin-bottom: 4px;">
        <hr style="border: none; border-top: 2px dashed black; width: 15px; float: left; margin-top: 6px; margin-right: 8px;">
        <b>Cakupan Sensor ARG</b>
    </div>
</div>
'''

# ==========================================
# 2. KOTAK LEGEND STATUS PERINGATAN (Posisi Bawah - Gabungan)
# ==========================================
legend_peringatan = '''
<div style="
    position: fixed; 
    bottom: 30px; left: 30px; width: 230px; height: auto; 
    background-color: rgba(255, 255, 255, 0.9); 
    border: 2px solid grey; z-index: 9999; 
    font-size: 12px; padding: 10px; border-radius: 8px; 
    box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;
">
    <h4 style="margin-top: 0; margin-bottom: 10px; font-size: 14px; text-align: center; color: black;"><b>Status Peringatan</b></h4>
    
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">

    <div style="margin-bottom: 5px; font-weight: bold; color: #333;">Intensitas Hujan (24 Jam):</div>
    
    <div style="margin-bottom: 6px; height: 18px;">
        <div style="background: blue; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">
            <i class="glyphicon glyphicon-cloud"></i>
        </div>
        <span style="line-height: 18px;">Cerah (0 mm)</span>
    </div>
    
    <div style="margin-bottom: 6px; height: 18px;">
        <div style="background: green; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">
            <i class="glyphicon glyphicon-tint"></i>
        </div>
        <span style="line-height: 18px;">Ringan (0.1 - 20 mm)</span>
    </div>
    
    <div style="margin-bottom: 6px; height: 18px;">
        <div style="background: beige; border-radius: 50%; width: 18px; height: 18px; color: black; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px; border: 1px solid #ccc;">
            <i class="glyphicon glyphicon-tint"></i>
        </div>
        <span style="line-height: 18px;">Sedang (20 - 50 mm)</span>
    </div>
    
    <div style="margin-bottom: 6px; height: 18px;">
        <div style="background: orange; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">
            <i class="glyphicon glyphicon-info-sign"></i>
        </div>
        <span style="line-height: 18px;">Lebat (50 - 100 mm)</span> 
    </div>
    
    <div style="margin-bottom: 6px; height: 18px;">
        <div style="background: red; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">
            <i class="glyphicon glyphicon-warning-sign"></i>
        </div>
        <span style="line-height: 18px;">Sangat Lebat (100 - 150 mm)</span>
    </div>
    
    <div style="margin-bottom: 6px; height: 18px;">
        <div style="background: darkred; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">
            <i class="glyphicon glyphicon-flash"></i>
        </div>
        <span style="line-height: 18px;">Ekstrem (> 150 mm)</span>
    </div>

    <hr style="margin: 8px 0; border-top: 1px dashed #999;">

    <div style="margin-bottom: 5px; font-weight: bold; color: #333;">Level Peringatan Area:</div>
    <div style="margin-bottom: 4px; height: 14px;"><i style="background: orange; opacity: 0.8; width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 2px; margin-top: 1px;"></i><span style="line-height: 14px;">Waspada</span></div>
    <div style="margin-bottom: 4px; height: 14px;"><i style="background: red; opacity: 0.8; width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 2px; margin-top: 1px;"></i><span style="line-height: 14px;">Siaga</span></div>
    <div style="margin-bottom: 0px; height: 14px;"><i style="background: darkred; opacity: 0.8; width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 2px; margin-top: 1px;"></i><span style="line-height: 14px;">Awas</span></div>
</div>
'''

# Masukin 2 Kotak Baru ke Peta Utama
m.get_root().html.add_child(folium.Element(legend_bahaya))
m.get_root().html.add_child(folium.Element(legend_peringatan))
# Tambahin ini kalau belum ada (Cukup 1 kali aja nulisnya di paling bawah peta)
folium.LayerControl().add_to(m)

st_folium(m, height=650, width="stretch", returned_objects=[])

st.divider() 

# ==========================================
# TOMBOL DOWNLOAD PETA (INTERAKTIF HTML)
# ==========================================
# 1. Save peta yang udah jadi (dengan semua overlay & pin) ke dalam file sementara
nama_file_peta = "Peta_EWS_NTB_Terbaru.html"
m.save(nama_file_peta)

# 2. Bikin tombol download di Streamlit
st.markdown("---") # Bikin garis pemisah
with open(nama_file_peta, "rb") as file:
    st.download_button(
        label="📥 Download Peta EWS (Interactive HTML)",
        data=file,
        file_name=nama_file_peta,
        mime="text/html",
        help="Download peta ini untuk dibuka secara offline di browser (Chrome/Edge/Firefox)"
    )

# ==========================================
# 2. PANEL TOMBOL FISIK (Taruh di bawah peta, di atas tabel)
# ==========================================
#st.markdown("---") # Garis pembatas estetik

# Trik 5 Kolom: Kolom ujung digedein (rasio 2) biar neken 3 kolom tengah
col_spasi1, col_btn1, col_btn2, col_btn3, col_spasi2 = st.columns([2, 1, 1, 1, 2])

# Tombolnya ukurannya ngepas teks aja (gak usah use_container_width=True)
with col_btn1:
    # Kalau diklik, ngirim angka 2 (H-2) ke fungsi set_hari
    st.button("⏮️ Data H-2", on_click=set_hari, args=(2,)) 
with col_btn2:
    # Kalau diklik, ngirim angka 1 (Kemarin)
    st.button("⏪ Data H-1", on_click=set_hari, args=(1,))
with col_btn3:
    # Kalau diklik, ngirim angka 0 (Hari Ini)
    st.button("✅ Data Hari Ini", on_click=set_hari, args=(0,))

# ==========================================
# TEKS INFO TANGGAL DI BAWAH TOMBOL
# ==========================================
tanggal_pilih = date.today() - timedelta(days=st.session_state.offset_hari)

if st.session_state.offset_hari == 0:
    label = f"Menampilkan Data Hari ini ({tanggal_pilih.strftime('%d %B %Y')})"
elif st.session_state.offset_hari == 1:
    label = f"Menampilkan Data Kemarin ({tanggal_pilih.strftime('%d %B %Y')})"
else:
    label = f"Menampilkan Data Selumbari ({tanggal_pilih.strftime('%d %B %Y')})"

# Teks di-center rapi di bawah tombol
st.markdown(f"<h5 style='text-align: center; color: #1f77b4; margin-top: 15px;'>📅 {label}</h5>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True) # Spasi sebelum masuk ke tabel
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
            'Kab/Kota': item['nama_kota'],
            'Hujan (mm)': curah,
            'Intensitas': kategori_teks,
            'Status Area': status_teks,
            'Update Terakhir (UTC)': item['tanggal']
        })

# Convert data list ke DataFrame Pandas
    df = pd.DataFrame(tabel_data)

    # ascending=False artinya dari Besar ke Kecil (Descending)
    df = df.sort_values(by="Hujan (mm)", ascending=False)

    # --- JURUS PANDAS STYLER (RATA TENGAH & FORMAT ANGKA) ---
    kolom_center = ["Kab/Kota", "Hujan (mm)", "Intensitas", "Status Area"]

    styled_df = df.style.set_properties(
        subset=kolom_center, 
        **{'text-align': 'center'}
    ).set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center')]}
    ]).format(
        {"Hujan (mm)": "{:.1f}"} # <--- INI OBATNYA BRO! Bikin angkanya jadi 1 digit di belakang koma
    )

    # Tampilkan tabel yang udah di-style ke Streamlit
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

# Nah, 'else' ini posisinya lurus sama 'if' utama yang di atas banget (sebelum gambar)
else:
    st.warning("Data API masih kosong / belum ketarik.")









































































