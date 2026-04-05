import json
import os
import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import pytz
import xml.etree.ElementTree as ET
from streamlit_autorefresh import st_autorefresh
import time
from branca.element import MacroElement, Template
import streamlit.components.v1 as components

# ==========================================
# ATUR JUDUL TAB BROWSER & BIKIN FULL LAYAR
# ==========================================
st.set_page_config(
    page_title="Dashboard Peringatan Dini Longsor dan Banjir NTB",
    page_icon="https://www.bmkg.go.id/asset/img/logo/logo-bmkg.png",
    layout="wide"
)

# ==========================================
# FITUR AUTO-REFRESH MODE TV DISPLAY
# ==========================================
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
            padding-top: 28px !important; /* Tinggi fix untuk top-time-bar */
            padding-bottom: 0rem !important;
        }}
        header {{display: none !important;}} 
        [data-testid="stToolbar"] {{display: none !important;}} 
        
        /* 2. Bikin Baris Waktu di Paling Atas (Fixed) */
        .top-time-bar {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 28px;
            background-color: #ffffff;
            border-bottom: 1px solid #e0e0e0;
            z-index: 99999;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 30px;
            font-size: 11px;
            color: #0056b3;
            font-weight: bold;
            letter-spacing: 0.5px;
        }}
        
        /* 3. WADAH HEADER: KITA BETOT KE ATAS! */
        .ofs-header-container {{
            margin-top: -20px !important; /* <--- JURUS BETOT: Tarik logo ke atas nabrak baris waktu */
        }}

        .ofs-header {{
            display: flex;
            align-items: center;
            padding: 0px 30px 5px 30px;
        }}
        .ofs-header img {{
            width: 50px;
            margin-right: 15px;
        }}
        .ofs-title h3 {{
            margin: 0 !important;
            padding: 0 !important;
            color: #002B5B; 
            font-size: 20px;
            font-weight: 800;
            line-height: 1.2;
        }}
        .ofs-title p {{
            margin: 0 !important;
            padding: 0 !important;
            color: #444;
            font-size: 15px;
            line-height: 1.2;
        }}
        
        /* 4. GARIS BIRU: Kasih jarak bawah biar nggak ditelan peta */
        .garis-biru {{
            margin: 0 30px 10px 30px !important; /* Kasih 10px di bawah garis */
            border: none !important;
            border-bottom: 2px solid #002B5B !important;
        }}

        /* 5. NORMALIASI PETA: Jangan ditarik ke atas lagi! */
        iframe[title="streamlit_folium.st_folium"] {{
            margin-top: 0px !important; /* <--- OBAT GARIS KETUTUP: Bikin 0 biar garis birunya kelihatan */
        }}
    </style>

    <div class="top-time-bar">
        <div>{tanggal_str}</div>
        <div id="jam-live">STANDAR WAKTU INDONESIA &nbsp;&nbsp;:&nbsp;&nbsp; {waktu_utc_str}</div>
    </div>
    
    <div class="ofs-header-container">
        <div class="ofs-header">
            <img src="https://www.bmkg.go.id/asset/img/logo/logo-bmkg.png">
            <div class="ofs-title">
                <h3>Stasiun Meteorologi ZAM Lombok</h3>
                <p>Dashboard Peringatan Dini Longsor dan Banjir Nusa Tenggara Barat</p>
            </div>
        </div>
        <hr class="garis-biru">
    </div>
""", unsafe_allow_html=True)

# ==========================================
# JURUS JAVASCRIPT: BIKIN JAM BERDETAK TIAP DETIK
# ==========================================
components.html("""
<script>
    setInterval(function() {
        var now = new Date();
        
        // Ambil jam UTC (karena lu pakenya format UTC di atas)
        var h = now.getUTCHours().toString().padStart(2, '0');
        var m = now.getUTCMinutes().toString().padStart(2, '0');
        var s = now.getUTCSeconds().toString().padStart(2, '0');
        
        var jamStr = "STANDAR WAKTU INDONESIA &nbsp;&nbsp;:&nbsp;&nbsp; " + h + ":" + m + ":" + s + " UTC";
        
        // Tembak langsung ke ID 'jam-live' di layar utama Streamlit
        var clockEl = window.parent.document.getElementById('jam-live');
        if (clockEl) {
            clockEl.innerHTML = jamStr;
        }
    }, 1000); // 1000 milidetik = 1 detik
</script>
""", height=0, width=0)

# ==========================================
# OTAK MESIN WAKTU 
# ==========================================
if 'offset_hari' not in st.session_state:
    st.session_state.offset_hari = 0

def set_hari(offset):
    st.session_state.offset_hari = offset

tanggal_pilih = date.today() - timedelta(days=st.session_state.offset_hari)
tanggal_api = tanggal_pilih.strftime("%Y-%m-%d")

# ==========================================
# FUNGSI NARIK DATA DARI MULTIPLE AKUN AWSCENTER
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

# ==========================================
# LOGIKA PINTAR PENARIKAN DATA (LIVE vs HISTORI)
# ==========================================
data_sensor = [] 

if st.session_state.offset_hari == 0:
    with st.spinner("Sedang menarik data Real-Time dari AWS Center..."):
        data_sensor = ambil_data_live()
        if not data_sensor:
            st.error("Gagal menarik data Live / Data kosong.")

elif st.session_state.offset_hari == 1:
    if os.path.exists('data_h1.json'):
        with open('data_h1.json', 'r') as f:
            data_sensor = json.load(f)
    else:
        st.warning("⚠️ Data histori Kemarin belum tersedia. Robot GitHub belum narik datanya semalam.")

elif st.session_state.offset_hari == 2:
    if os.path.exists('data_h2.json'):
        with open('data_h2.json', 'r') as f:
            data_sensor = json.load(f)
    else:
        st.warning("⚠️ Data histori H-2 belum tersedia.")

# ==========================================
# 1. BIKIN PETA KOSONG
# ==========================================
m = folium.Map(location=[-8.65, 117.36], zoom_start=8.5, tiles=None, attributionControl=False)
# Bikin lantai khusus biar titik AWS selalu di atas poligon (z-index 620)
folium.map.CustomPane('lantai_titik_aws', z_index=620).add_to(m)

# ==========================================
# 2. PILIHAN BASEMAP
# ==========================================
folium.TileLayer(
    tiles='http://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}',
    attr=' ',
    name='Google Maps (Standar)',
    overlay=False,
    control=True
).add_to(m)

folium.TileLayer(
    tiles='http://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}',
    attr=' ',
    name='Google Satellite (Satelit)',
    overlay=False,
    control=True,
    show=False
).add_to(m)

# ==========================================
# FUNGSI WARNA ZONA
# ==========================================
def style_kerentanan(feature):
    kategori = str(feature['properties'].get('REMARK', '')).upper()
    if 'SANGAT TINGGI' in kategori: res = {'fillColor': '#cc0000', 'color': '#cc0000', 'weight': 0.5, 'fillOpacity': 0.4}
    elif 'TINGGI' in kategori: res = {'fillColor': '#ff3385', 'color': '#ff3385', 'weight': 0.5, 'fillOpacity': 0.4}
    elif 'MENENGAH' in kategori or 'SEDANG' in kategori: res = {'fillColor': '#ffff00', 'color': '#ffff00', 'weight': 0.5, 'fillOpacity': 0.4}
    elif 'SANGAT RENDAH' in kategori: res = {'fillColor': '#00ccff', 'color': '#00ccff', 'weight': 0.5, 'fillOpacity': 0.4}
    else: res = {'fillColor': '#00cc00', 'color': '#00cc00', 'weight': 0.5, 'fillOpacity': 0.2}
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

# ==========================================
# PEMBUATAN PIN SENSOR (HACK DIVICON - ALWAYS ON TOP)
# ==========================================
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
            if curah == 0: kategori, status_area, fill_warna = "Cerah / Berawan", "Aman", "blue"
            elif 0 < curah <= 20: kategori, status_area, fill_warna = "Hujan Ringan", "Aman", "green"
            else: kategori, status_area, fill_warna = "Hujan Sedang", "Aman", "#F5DEB3" 

            # INI DIA OBATNYA BRO! Kita bikin titik buletnya pake CSS HTML murni!
            html_dot = f'''
            <div style="background-color: {fill_warna}; border-radius: 50%; width: 12px; height: 12px; border: 2px solid black; box-shadow: 1px 1px 4px rgba(0,0,0,0.6);"></div>
            '''

            # Karena pakenya folium.Marker + DivIcon, dia OTOMATIS pindah ke Lantai Atas!
            folium.Marker(
                location=[lat, lon],
                popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Curah Hujan: <b>{curah} mm</b><br>Kategori: <b>{kategori}</b><br>Status Area: <b>{status_area}</b><br><small>Update: {tanggal} UTC</small></div>", 
                tooltip=f"{nama}: {curah} mm ({kategori})",
                icon=folium.DivIcon(html=html_dot)
            ).add_to(m)
            
        else:
            if 50 <= curah <= 100: kategori, status_area, warna, ikon, warna_ikon = "Hujan Lebat", "WASPADA", "orange", "info-sign", "white"
            elif 100 < curah <= 150: kategori, status_area, warna, ikon, warna_ikon = "Hujan Sangat Lebat", "SIAGA", "red", "warning-sign", "white"
            else: kategori, status_area, warna, ikon, warna_ikon = "Hujan Ekstrem", "AWAS", "darkred", "flash", "white"
            
            folium.Marker(
                [lat, lon], popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Curah Hujan: <b>{curah} mm</b><br>Kategori: <b>{kategori}</b><br>Status Area: <b>{status_area}</b><br><small>Update: {tanggal} UTC</small></div>", tooltip=f"{nama} ({kategori})", icon=folium.Icon(color=warna, icon=ikon, icon_color=warna_ikon)
            ).add_to(m)

    except Exception as e:
        continue
        
# ==========================================
# FUNGSI NARIK DATA CUACA BMKG (SESUAI ATURAN RESMI PUSAT)
# ==========================================
# ATURAN 1: Update pusat cuma 2x sehari. Jadi kita cache 1 JAM (3600 detik). 
# Biar aman total dari limit 60 request/menit!
@st.cache_data(ttl=3600) 
def ambil_cuaca_bmkg():
    data_cuaca_gabungan = []
    
    # ATURAN 2: Pakai adm4. Kita set 15 Titik Merata se-NTB
    lokasi_pilihan = [
        "52.08.05.2004", # Malaka (Pusuk Gunung Sari)
        "52.02.12.2006", # Aik Berik (Batukliang Utara)
        "52.03.15.2001", # Sembalun Bumbung (Pusuk Sembalun)
        "52.01.07.2002", # Sekotong Barat (Sekotong)
        "52.07.04.2001", # Sekongkang Atas (Sekongkang Atas)
        "52.04.07.2003", # Bao Desa (Batu Lanteh)
        "52.04.11.2008", # Ropang (Ropang)
        "52.06.11.2006", # Doro O'o (Langgudu)
        "52.06.15.2005", # Sai (Soromandi)
        "52.06.14.2003", # Kawinda Toi (Tambora)
    ]
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    
    for kode in lokasi_pilihan:
        try:
            url_api = f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={kode}"
            response = session.get(url_api, timeout=10)
            
            if response.status_code == 200:
                data_json = response.json()
                if isinstance(data_json, dict) and 'data' in data_json:
                    data_list = data_json['data']
                    if len(data_list) > 0:
                        data_cuaca_gabungan.append(data_list[0])
            
            # CEGATAN LIMIT: Kalau BMKG ngirim error 429 (Too Many Requests), berhentiin tarikan!
            elif response.status_code == 429:
                break
                
            # ATURAN 3: Jeda sopan santun biar gak dikira nge-DDoS
            time.sleep(0.5) 
            
        except Exception as e:
            continue
            
    return data_cuaca_gabungan

# ==========================================
# LAYER TAMBAHAN: PRAKIRAAN CUACA BMKG
# ==========================================
layer_prakiraan = folium.FeatureGroup(name="🌤️ Prakiraan Cuaca BMKG (Se-NTB)", show=False)

with st.spinner("📡 Menyinkronkan Data Cuaca BMKG..."):
    data_cuaca_bmkg = ambil_cuaca_bmkg()
    
    # PENGHANCUR CACHE: Kalau gagal narik data, hapus memori kosongnya!
    if not data_cuaca_bmkg:
        st.cache_data.clear()

if data_cuaca_bmkg:
    icon_cuaca = {
        "Cerah": "☀️", "Cerah Berawan": "⛅", "Berawan": "☁️", "Berawan Tebal": "☁️",
        "Udara Kabur": "🌫️", "Asap": "🌫️", "Kabut": "🌫️",
        "Hujan Ringan": "🌧️", "Hujan Sedang": "🌧️", "Hujan Lebat": "⛈️",
        "Hujan Lokal": "🌦️", "Hujan Petir": "🌩️"
    }

    for item in data_cuaca_bmkg:
        try:
            lokasi = item.get('lokasi', {})
            nama_kec = lokasi.get('kecamatan', 'Lokasi')
            nama_kab = lokasi.get('kotkab', '')
            
            lat = float(lokasi.get('lat', 0))
            lon = float(lokasi.get('lon', 0))
            if lat == 0 and lon == 0: continue
            
            cuaca_list = item.get('cuaca', [])
            keterangan = "Berawan"
            
            if cuaca_list and len(cuaca_list) > 0 and isinstance(cuaca_list[0], list):
                if len(cuaca_list[0]) > 0:
                    data_saat_ini = cuaca_list[0][0]
                    keterangan = data_saat_ini.get('weather_desc', 'Berawan')

            emoji = icon_cuaca.get(keterangan, "☁️")
            
            html_icon = f"""
            <div style="font-size:16px; background:rgba(255,255,255,0.85); border-radius:50%; width:26px; height:26px; display:flex; justify-content:center; align-items:center; box-shadow:1px 1px 3px rgba(0,0,0,0.5); border:1px solid #777;">
                {emoji}
            </div>
            """
            
            folium.Marker(
                location=[lat, lon], 
                tooltip=f"<b>Kec. {nama_kec}</b>: {keterangan}",
                popup=f"<div style='min-width: 140px; text-align:center;'><b>📍 Kec. {nama_kec}</b><br><span style='font-size:35px;'>{emoji}</span><br><b>{keterangan}</b><br><small>{nama_kab}</small></div>",
                icon=folium.DivIcon(html=html_icon)
            ).add_to(layer_prakiraan)
            
        except Exception as e:
            continue
            
# Masukin ke Peta
layer_prakiraan.add_to(m)

# ==========================================
# FUNGSI NARIK DATA PERINGATAN DINI (THE ULTIMATE FIX)
# ==========================================
@st.cache_data(ttl=60) 
def ambil_peringatan_dini():
    peringatan_aktif = []
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    try:
        url_rss = f"https://www.bmkg.go.id/alerts/nowcast/id/rss.xml?t={int(time.time())}"
        res_rss = session.get(url_rss, timeout=10)
        
        if res_rss.status_code == 200:
            import xml.etree.ElementTree as ET
            import re
            
            rss_text = re.sub(r' xmlns="[^"]+"', '', res_rss.text)
            root_rss = ET.fromstring(rss_text)
            
            for item in root_rss.findall('.//item'):
                title = item.findtext('title', '')
                
                if 'Nusa Tenggara Barat' in title or 'NTB' in title or 'NUSA TENGGARA BARAT' in title:
                    link_detail = item.findtext('link', '')
                    if link_detail:
                        link_fresh = f"{link_detail}?t={int(time.time())}"
                        res_cap = session.get(link_fresh, timeout=10)
                        
                        if res_cap.status_code == 200:
                            cap_text = re.sub(r' xmlns="[^"]+"', '', res_cap.text)
                            cap_root = ET.fromstring(cap_text)
                            
                            # 1. Ambil HANYA wadah <info> Bahasa Indonesia
                            info_blocks = [i for i in cap_root.findall('.//info') if 'id' in i.findtext('language', '').lower()]
                            
                            # 2. LOOP WADAH (KUNCI: WARNA DITENTUKAN DI SINI, BUKAN DI DALAM KECAMATAN!)
                            for idx_info, info in enumerate(info_blocks):
                                event = info.findtext('event', 'Peringatan Dini Cuaca')
                                headline = info.findtext('headline', '-')
                                desc = info.findtext('description', '-')
                                effective = info.findtext('effective', '-')
                                expires = info.findtext('expires', '-')
                                
                                # Logika Murni Pusat: Wadah 1 (index 0) = Oren, Wadah 2 (index 1) = Kuning
                                warna_poly = 'orange' if idx_info == 0 else 'yellow'
                                
                                # Backup validasi pakai Severity resmi CAP Internasional
                                severity = info.findtext('severity', '').lower()
                                if severity in ['moderate', 'minor']:
                                    warna_poly = 'yellow'
                                elif severity in ['severe', 'extreme']:
                                    warna_poly = 'orange'
                                    
                                opacity_poly = 0.6 if warna_poly == 'orange' else 0.4
                                
                                # 3. LOOP AREA/KECAMATAN (Haram ganti warna poly di dalam sini!)
                                for area in info.findall('.//area'):
                                    area_desc = area.findtext('areaDesc', 'Wilayah Terdampak')
                                    for poly in area.findall('.//polygon'):
                                        poly_text = poly.text
                                        if poly_text:
                                            coords = []
                                            for pt in poly_text.strip().split():
                                                if ',' in pt:
                                                    lat_s, lon_s = pt.split(',')
                                                    coords.append((float(lat_s), float(lon_s)))
                                            
                                            if coords:
                                                peringatan_aktif.append({
                                                    'coords': coords,
                                                    'warna': warna_poly,
                                                    'opacity': opacity_poly,
                                                    'nama_area': area_desc,
                                                    'event': event,
                                                    'description': desc,
                                                    'effective': effective,
                                                    'expires': expires
                                                })
                                                
            # 4. JURUS Z-INDEX (KARPET KUNING DIGELAR DULUAN, OREN DI ATASNYA)
            peringatan_aktif.sort(key=lambda x: 1 if x['warna'] == 'yellow' else 2)
            
    except Exception as e:
        pass 
        
    return peringatan_aktif

# ==========================================
# LAYER TAMBAHAN: POLYGON PERINGATAN DINI 
# ==========================================
layer_peringatan = folium.FeatureGroup(name="🚨 Peringatan Dini Cuaca", show=False)

with st.spinner("🚨 Mengecek Peringatan Dini Cuaca NTB..."):
    data_peringatan = ambil_peringatan_dini()

if data_peringatan and len(data_peringatan) > 0:
    for poly_dict in data_peringatan:
        folium.Polygon(
            locations=poly_dict['coords'],
            color=poly_dict['warna'],           
            weight=2,
            fill=True,
            fill_color=poly_dict['warna'],      
            fill_opacity=poly_dict['opacity'],      
            tooltip=f"<b>🚨 {poly_dict['event']}</b><br>{poly_dict['nama_area']}",
            popup=folium.Popup(
                f"<div style='min-width: 280px; max-height: 250px; overflow-y: auto;'><h4 style='color: #cc0000; margin-top:0;'>🚨 {poly_dict['event']}</h4><b>{poly_dict['nama_area']}</b><br><br><span style='font-size: 12px; color: #333;'>{poly_dict['description']}</span><br><br><hr style='margin: 5px 0;'><small style='color: #555;'><b>Mulai:</b> {poly_dict['effective']}<br><b>Berakhir:</b> {poly_dict['expires']}</small></div>", 
                max_width=350
            )
        ).add_to(layer_peringatan)

layer_peringatan.add_to(m)

# ==========================================
# TOMBOL REFRESH MENGAMBANG DI PETA
# ==========================================
tombol_refresh_html = """
<div style="position: absolute; top: 80px; left: 10px; z-index: 1000;">
    <button onclick="window.parent.location.reload(true);" title="Refresh Data BMKG" style="background-color: white; border: 2px solid rgba(0,0,0,0.2); border-radius: 4px; width: 34px; height: 34px; font-size: 18px; cursor: pointer; box-shadow: 0 1px 5px rgba(0,0,0,0.65); display: flex; justify-content: center; align-items: center;">
        🔄
    </button>
</div>
"""
m.get_root().html.add_child(folium.Element(tombol_refresh_html))

# ==========================================
# HTML LEGEND (FLEXBOX DESIGN: RAPI & DINAMIS!)
# ==========================================
legend_html = '''
<div style="position: fixed; bottom: 30px; left: 30px; display: flex; gap: 15px; z-index: 9999; align-items: flex-end;">
    
    <div id="legend_longsor" style="display: none; width: 210px; background-color: rgba(255, 255, 255, 0.9); border: 2px solid grey; font-size: 12px; padding: 10px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;">
        <h4 style="margin-top: 0; margin-bottom: 10px; font-size: 14px; text-align: center;"><b>Kerentanan Gerakan Tanah</b></h4>
        <div style="margin-bottom: 2px;"><i style="background: #cc0000; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Sangat Tinggi</div>
        <div style="margin-bottom: 2px;"><i style="background: #ff3385; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Tinggi</div>
        <div style="margin-bottom: 2px;"><i style="background: #ffff00; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Menengah</div>
        <div style="margin-bottom: 2px;"><i style="background: #00cc00; opacity: 0.3; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Rendah</div>
        <div style="margin-bottom: 2px;"><i style="background: #00ccff; opacity: 0.3; width: 12px; height: 12px; float: left; margin-right: 8px;"></i>Sangat Rendah</div>
    </div>
    
    <div id="legend_banjir" style="display: none; width: 190px; background-color: rgba(255, 255, 255, 0.9); border: 2px solid #0000FF; font-size: 12px; padding: 10px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;">
        <h4 style="margin-top: 0; margin-bottom: 10px; font-size: 14px; text-align: center;"><b>Kerentanan Banjir</b></h4>
        <div style="margin-bottom: 4px;"><i style="background:#00008B; width:15px; height:15px; float:left; margin-right:8px; opacity:0.5;"></i> Rawan Banjir (InaRISK)</div>
    </div>
</div>

<div style="position: fixed; bottom: 30px; right: 30px; display: flex; flex-direction: row-reverse; gap: 15px; z-index: 9999; align-items: flex-end;">
    
    <div id="legend_hujan" style="width: 220px; background-color: rgba(255, 255, 255, 0.9); border: 2px solid grey; font-size: 12px; padding: 10px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;">
        <h4 style="margin-top: 0; margin-bottom: 10px; font-size: 14px; text-align: center;"><b>Status Peringatan AWS</b></h4>
        <div style="margin-bottom: 5px; font-weight: bold;">Intensitas Hujan (24 Jam):</div>
        <div style="margin-bottom: 6px; height: 18px;"><div style="background: blue; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">☁</div><span style="line-height: 18px;">Cerah (0 mm)</span></div>
        <div style="margin-bottom: 6px; height: 18px;"><div style="background: green; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">🌧</div><span style="line-height: 18px;">Ringan (0.1 - 20 mm)</span></div>
        <div style="margin-bottom: 6px; height: 18px;"><div style="background: beige; border-radius: 50%; width: 18px; height: 18px; color: black; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px; border: 1px solid #ccc;">🌧</div><span style="line-height: 18px;">Sedang (20 - 50 mm)</span></div>
        <div style="margin-bottom: 6px; height: 18px;"><div style="background: orange; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">⚠</div><span style="line-height: 18px;">Lebat (50 - 100 mm)</span> </div>
        <div style="margin-bottom: 6px; height: 18px;"><div style="background: red; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">⚠</div><span style="line-height: 18px;">Sangat Lebat (100 - 150 mm)</span></div>
        <div style="margin-bottom: 6px; height: 18px;"><div style="background: darkred; border-radius: 50%; width: 18px; height: 18px; color: white; text-align: center; line-height: 18px; float: left; margin-right: 8px; font-size: 10px;">⚡</div><span style="line-height: 18px;">Ekstrem (> 150 mm)</span></div>
    </div>

    <div id="legend_nowcast" style="display: none; width: 210px; background-color: rgba(255, 255, 255, 0.9); border: 2px solid darkorange; font-size: 12px; padding: 10px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;">
        <h4 style="margin-top: 0; margin-bottom: 10px; font-size: 14px; text-align: center;"><b>Peringatan Dini (Nowcast)</b></h4>
        <div style="margin-bottom: 4px; height: 14px;"><i style="background: orange; border: 1px solid darkorange; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i><span>Wilayah Peringatan Dini</span></div>
        <div style="margin-bottom: 4px; height: 14px;"><i style="background: yellow; border: 1px solid gold; opacity: 0.6; width: 12px; height: 12px; float: left; margin-right: 8px;"></i><span>Wilayah Potensi Meluas</span></div>
    </div>
    
    <div id="legend_area_aws" style="width: 190px; background-color: rgba(255, 255, 255, 0.9); border: 2px solid grey; font-size: 12px; padding: 10px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3); color: black;">
        <h4 style="margin-top: 0; margin-bottom: 10px; font-size: 14px; text-align: center;"><b>Peringatan Area AWS</b></h4>
        <div style="margin-bottom: 4px; height: 14px;"><i style="background: orange; width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 2px;"></i><span>Waspada</span></div>
        <div style="margin-bottom: 4px; height: 14px;"><i style="background: red; width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 2px;"></i><span>Siaga</span></div>
        <div style="margin-bottom: 0px; height: 14px;"><i style="background: darkred; width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 2px;"></i><span>Awas</span></div>
    </div>

</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

# ==========================================
# MACRO ELEMENT LEAFLET (SUNTIKAN NATIVE ANTI-GAGAL)
# ==========================================
class LegendDinamis(MacroElement):
    def __init__(self):
        super(LegendDinamis, self).__init__()
        self._template = Template(u"""
        {% macro script(this, kwargs) %}
        var mapInstance = {{this._parent.get_name()}};
        
        mapInstance.on('overlayadd', function(e) {
            if (e.name.includes('Peringatan Dini Cuaca')) {
                document.getElementById('legend_nowcast').style.display = 'block';
            } else if (e.name.includes('Gerakan Tanah')) {
                document.getElementById('legend_longsor').style.display = 'block';
            } else if (e.name.includes('Banjir (InaRISK)')) {
                document.getElementById('legend_banjir').style.display = 'block';
            }
        });
        
        mapInstance.on('overlayremove', function(e) {
            if (e.name.includes('Peringatan Dini Cuaca')) {
                document.getElementById('legend_nowcast').style.display = 'none';
            } else if (e.name.includes('Gerakan Tanah')) {
                document.getElementById('legend_longsor').style.display = 'none';
            } else if (e.name.includes('Banjir (InaRISK)')) {
                document.getElementById('legend_banjir').style.display = 'none';
            }
        });
        {% endmacro %}
        """)

m.add_child(LegendDinamis())
folium.LayerControl().add_to(m)

# TAMPILKAN PETA UTAMA
st_folium(m, height=650, width="stretch", returned_objects=[])


# ==========================================
# PANEL TOMBOL (DOWNLOAD & KONTROL WAKTU SEJAJAR)
# ==========================================
# 1. Save peta yang udah jadi ke dalam file sementara
nama_file_peta = "Peta_EWS_NTB_Terbaru.html"
m.save(nama_file_peta)

st.markdown("<br>", unsafe_allow_html=True) # Spasi enter dikit aja biar gak nabrak peta banget

# 2. Bikin 4 Kolom Sejajar. Kolom pertama (rasio 2) agak lebar buat nampung teks Download.
col_dl, col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1, 1, 1])

with col_dl:
    with open(nama_file_peta, "rb") as file:
        st.download_button(
            label="📥 Download Peta EWS (Interactive HTML)",
            data=file,
            file_name=nama_file_peta,
            mime="text/html",
            help="Download peta ini untuk dibuka secara offline di browser",
            use_container_width=True # Biar tombolnya nge-full penuhin kolom
        )

with col_btn1:
    st.button("⏮️ Data H-2", on_click=set_hari, args=(2,), use_container_width=True) 
with col_btn2:
    st.button("⏪ Data H-1", on_click=set_hari, args=(1,), use_container_width=True)
with col_btn3:
    st.button("✅ Data Hari Ini", on_click=set_hari, args=(0,), use_container_width=True)

# ==========================================
# TEKS INFO TANGGAL 
# ==========================================
tanggal_pilih = date.today() - timedelta(days=st.session_state.offset_hari)

if st.session_state.offset_hari == 0:
    label = f"Menampilkan Data Hari ini ({tanggal_pilih.strftime('%d %B %Y')})"
elif st.session_state.offset_hari == 1:
    label = f"Menampilkan Data Kemarin ({tanggal_pilih.strftime('%d %B %Y')})"
else:
    label = f"Menampilkan Data Selumbari ({tanggal_pilih.strftime('%d %B %Y')})"

st.markdown(f"<h5 style='text-align: center; color: #1f77b4; margin-top: 15px;'>📅 {label}</h5>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True) 

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

    # Pembuatan DataFrame wajib di dalam blok if data_sensor ini
    df = pd.DataFrame(tabel_data)
    df = df.sort_values(by="Hujan (mm)", ascending=False)

    kolom_center = ["Kab/Kota", "Hujan (mm)", "Intensitas", "Status Area"]
    styled_df = df.style.set_properties(
        subset=kolom_center, 
        **{'text-align': 'center'}
    ).set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center')]}
    ]).format(
        {"Hujan (mm)": "{:.1f}"} 
    )

    st.dataframe(styled_df, use_container_width=True, hide_index=True)

else:
    st.warning("Data API masih kosong / belum ketarik.")
