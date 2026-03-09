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
from branca.element import Template, MacroElement

# Atur Judul Tab Browser & Bikin Full Layar
st.set_page_config(page_title="Peta Longsor NTB", layout="wide")

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
            <p>Peta Peringatan Dini Longsor NTB</p>
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
    # --- JALUR LUSA (H-2) ---
    if os.path.exists('data_h2.json'):
        with open('data_h2.json', 'r') as f:
            data_sensor = json.load(f)
    else:
        st.warning("⚠️ Data histori H-2 belum tersedia.")

# ==========================================
# 1. BIKIN PETA KOSONG (HAPUS BASEMAP BAWAAN)
# ==========================================
# Ganti koordinat & zoom sesuai titik tengah NTB lu
m = folium.Map(location=[-8.65, 117.36], zoom_start=8.5, tiles=None)

# --- INI JURUS SUNTIKANNYA BRO! Bikin semua logo ukurannya rata dan tebal ---
fix_icon_size = """
<style>
.awesome-marker i {
    font-size: 16px !important;    /* Paksa ukurannya sama semua */
    font-weight: bold !important;  /* Paksa cetak tebal biar gak ceking */
}
</style>
"""
m.get_root().header.add_child(folium.Element(fix_icon_size))

# ==========================================
# 2. LAPISAN BAWAH: DARATAN & JALAN (TANPA TEKS)
# ==========================================
folium.TileLayer(
    tiles='https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png',
    attr='&copy; <a href="https://carto.com/">CartoDB</a>',
    name='Basemap',
    overlay=False
).add_to(m)

# ==========================================
# 5. LAPISAN TENGAH-ATAS: BATAS KEKUASAAN ARG (THIESSEN)
# ==========================================
try:
    folium.GeoJson(
        "batas_arg.geojson",
        name="Wilayah Cakupan ARG",
        style_function=lambda x: {
            'color': 'black',       # Warna garis batas hitam
            'weight': 1.5,          # Ketebalan garis
            'dashArray': '5, 5',    # Bikin garisnya putus-putus biar estetik
            'fillOpacity': 0        # Bolongin area dalamnya biar warna PVMBG tetep kelihatan
        }
    ).add_to(m)
except Exception as e:
    pass

# ==========================================
# 6. LAPISAN ATAS: TEKS NAMA KOTA / DAERAH AJA
# ==========================================
folium.TileLayer(
    tiles='https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png',
    attr='&copy; <a href="https://carto.com/">CartoDB</a>',
    name='Labels Daerah',
    overlay=True,
    control=False, # Biar gak usah muncul di menu centang peta
    pane='shadowPane'
).add_to(m)

# ==========================================
# FUNGSI PEWARNAAN OTOMATIS (STANDAR PVMBG / ESDM)
# ==========================================
def style_kerentanan(feature):
    # 🔴 PENTING: Ganti 'NAMA_KOLOM' sama nama kolom kategori di data lu (misal: 'KETERANGAN' atau 'KERENTANAN')
    kategori = str(feature['properties'].get('REMARK', '')).upper()
    
    # Mencocokkan dengan standar warna peta PVMBG
    if 'SANGAT TINGGI' in kategori:
        return {'fillColor': '#cc0000', 'color': '#cc0000', 'weight': 1, 'fillOpacity': 0.6} # Merah Tua
    elif 'TINGGI' in kategori:
        return {'fillColor': '#ff3385', 'color': '#ff3385', 'weight': 1, 'fillOpacity': 0.6} # Pink / Merah Muda
    elif 'MENENGAH' in kategori or 'SEDANG' in kategori:
        return {'fillColor': '#ffff00', 'color': '#ffff00', 'weight': 1, 'fillOpacity': 0.6} # Kuning
    elif 'SANGAT RENDAH' in kategori:
        return {'fillColor': '#00ccff', 'color': '#00ccff', 'weight': 1, 'fillOpacity': 0.3} # Biru Muda (Transparan dikit)
    else:
        # Default untuk Rendah / Aman
        return {'fillColor': '#00cc00', 'color': '#00cc00', 'weight': 1, 'fillOpacity': 0.3} # Hijau (Transparan dikit)

# ==========================================
# FUNGSI WARNA ZONA RAWAN BANJIR (INARISK BINARY)
# ==========================================
def style_banjir(feature):
    try:
        tingkat_bahaya = int(float(feature['properties'].get('DN', 0)))
    except:
        tingkat_bahaya = 0
        
    if tingkat_bahaya == 1:
        warna = '#00BFFF' # Biru Muda (Banjir)
        opacity = 0.5
    else:
        warna = '#000000'
        opacity = 0.0 
        
    return {'fillColor': warna, 'color': warna, 'weight': 0.5 if opacity > 0 else 0, 'fillOpacity': opacity}
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

# --- TAMBAHIN INI BUAT ZONA MERAH SUMBAWA/BIMA ---
#try:
 #   folium.GeoJson(
  #      "zona_merah_smb.geojson", # <--- GANTI PAKE NAMA FILE LU
   #     name="Zona Rawan Longsor Sumbawa dan Bima",
    #    style_function=lambda feature: {'fillColor': '#ff0000', 'color': '#cc0000', 'weight': 1, 'fillOpacity': 0.4}
    #).add_to(m)
#except Exception as e:
 #   pass

# LOGIKA KATEGORI HUJAN & STATUS AREA BMKG
for item in data_sensor:
    try:
        lat = float(item['lat'])
        lon = float(item['lng'])
        nama = item['name_station']
        curah_str = str(item['curah']).replace(',', '.')
        curah = float(curah_str) if curah_str.strip() != "" else 0.0

        # --- PERBAIKAN WARNA & LOGO ICON ---
        if curah == 0:
            kategori, status_area, warna, ikon, warna_ikon = "Cerah / Berawan", "Aman", "blue", "cloud", "white"
        elif 0 < curah <= 20:
            kategori, status_area, warna, ikon, warna_ikon = "Hujan Ringan", "Aman", "green", "tint", "white"
        elif 20 < curah <= 50:
            # KHUSUS SEDANG: Pin Beige (Kuning), Ikon Hitam biar kontras!
            kategori, status_area, warna, ikon, warna_ikon = "Hujan Sedang", "Aman", "beige", "tint", "black" 
        elif 50 < curah <= 100:
            kategori, status_area, warna, ikon, warna_ikon = "Hujan Lebat", "WASPADA", "orange", "info-sign", "white"
        elif 100 < curah <= 150:
            kategori, status_area, warna, ikon, warna_ikon = "Hujan Sangat Lebat", "SIAGA", "red", "warning-sign", "white"
        else: 
            kategori, status_area, warna, ikon, warna_ikon = "Hujan Ekstrem", "AWAS", "darkred", "flash", "white"
        # --- PERBAIKAN TEKS POPUP (Potensi -> Status Area) ---
        folium.Marker(
            [lat, lon],
            popup=f"<div style='min-width: 150px;'><b>{nama}</b><br>Curah Hujan: <b>{curah} mm</b><br>Kategori: <b>{kategori}</b><br>Status Area: <b>{status_area}</b><br><small>Update: {item['tanggal']} UTC</small></div>",
            tooltip=f"{nama} ({kategori})",
            icon=folium.Icon(color=warna, icon=ikon, icon_color=warna_ikon)
        ).add_to(m)
    except Exception as e:
        continue 

# ==========================================
# KOTAK LEGEND PINTAR (DINAMIS)
# ==========================================
legend_dinamis = """
{% macro html(this, kwargs) %}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
</head>
<body>
<div id='maplegend' class='maplegend' 
    style='position: absolute; z-index:9999; background-color:rgba(255, 255, 255, 0.9);
    border-radius:6px; padding: 10px; font-size:14px; left: 20px; bottom: 20px; border: 2px solid grey;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.3);'>
    
    <div id="legend-hujan">
        <strong>Kategori Hujan (24 Jam):</strong><br>
        <i style="background:#0000FF; width:12px; height:12px; float:left; margin-right:8px; margin-top:4px; border-radius:50%;"></i> Cerah (0 mm)<br>
        <i style="background:#008000; width:12px; height:12px; float:left; margin-right:8px; margin-top:4px; border-radius:50%;"></i> Ringan (0.1 - 20 mm)<br>
        <i style="background:#FFFF00; width:12px; height:12px; float:left; margin-right:8px; margin-top:4px; border-radius:50%;"></i> Sedang (20 - 50 mm)<br>
        <i style="background:#FFA500; width:12px; height:12px; float:left; margin-right:8px; margin-top:4px; border-radius:50%;"></i> Waspada (50 - 100 mm)<br>
        <i style="background:#FF0000; width:12px; height:12px; float:left; margin-right:8px; margin-top:4px; border-radius:50%;"></i> Siaga (100 - 150 mm)<br>
        <i style="background:#800000; width:12px; height:12px; float:left; margin-right:8px; margin-top:4px; border-radius:50%;"></i> Awas (> 150 mm)<br>
    </div>

    <div id="legend-longsor" style="display: none; margin-top: 10px; border-top: 1px solid #ccc; padding-top: 5px;">
        <strong>Kerentanan Gerakan Tanah:</strong><br>
        <i style="background:#FF0000; width:15px; height:15px; float:left; margin-right:8px; opacity:0.7;"></i> Sangat Tinggi<br>
        <i style="background:#FF69B4; width:15px; height:15px; float:left; margin-right:8px; opacity:0.7;"></i> Tinggi<br>
        <i style="background:#FFFF00; width:15px; height:15px; float:left; margin-right:8px; opacity:0.7;"></i> Menengah<br>
        <i style="background:#00FF00; width:15px; height:15px; float:left; margin-right:8px; opacity:0.7;"></i> Rendah<br>
        <i style="background:#00BFFF; width:15px; height:15px; float:left; margin-right:8px; opacity:0.7;"></i> Sangat Rendah<br>
    </div>

    <div id="legend-banjir" style="display: none; margin-top: 10px; border-top: 1px solid #ccc; padding-top: 5px;">
        <strong>Kerentanan Banjir:</strong><br>
        <i style="background:#00BFFF; width:15px; height:15px; float:left; margin-right:8px; opacity:0.5; border: 1px solid #0000FF;"></i> Rawan Banjir (InaRISK)<br>
    </div>
</div>
</body>
</html>

<script type="text/javascript">
  // JURUS SAKTI JAVASCRIPT: Nguping klik dari forecaster
  setTimeout(function() {
      var map_instance = null;
      for (var key in window) {
          if (key.match(/^map_[a-z0-9]+$/)) {
              var obj = window[key];
              if (typeof obj === 'object' && obj !== null && obj.on) {
                  map_instance = obj;
                  break;
              }
          }
      }
      
      if (map_instance) {
          // Kalau layer DICENTANG (Nyala)
          map_instance.on('overlayadd', function(e) {
              var nama_layer = e.name.toLowerCase();
              if (nama_layer.includes("longsor") || nama_layer.includes("tanah")) {
                  document.getElementById("legend-longsor").style.display = "block";
              }
              if (nama_layer.includes("banjir")) {
                  document.getElementById("legend-banjir").style.display = "block";
              }
          });

          // Kalau layer DI-UNCHECK (Mati)
          map_instance.on('overlayremove', function(e) {
              var nama_layer = e.name.toLowerCase();
              if (nama_layer.includes("longsor") || nama_layer.includes("tanah")) {
                  document.getElementById("legend-longsor").style.display = "none";
              }
              if (nama_layer.includes("banjir")) {
                  document.getElementById("legend-banjir").style.display = "none";
              }
          });
      }
  }, 1000);
</script>
{% endmacro %}
"""

# Masukin kodingan cerdas ini ke dalam peta utama (m)
macro = MacroElement()
macro._template = Template(legend_dinamis)
m.get_root().add_child(macro)

# Tambahin ini kalau belum ada (Cukup 1 kali aja nulisnya di paling bawah peta)
folium.LayerControl().add_to(m)

st_folium(m, height=650, width="stretch", returned_objects=[])

st.divider() 

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
    st.button("⏪ Data Kemarin", on_click=set_hari, args=(1,))
with col_btn3:
    # Kalau diklik, ngirim angka 0 (Hari Ini)
    st.button("✅ Data Hari Ini", on_click=set_hari, args=(0,))

# ==========================================
# TEKS INFO TANGGAL DI BAWAH TOMBOL
# ==========================================
tanggal_pilih = date.today() - timedelta(days=st.session_state.offset_hari)

if st.session_state.offset_hari == 0:
    label = f"Menampilkan Data HARI INI ({tanggal_pilih.strftime('%d %b %Y')})"
elif st.session_state.offset_hari == 1:
    label = f"Menampilkan Data KEMARIN ({tanggal_pilih.strftime('%d %b %Y')})"
else:
    label = f"Menampilkan Data H-2 ({tanggal_pilih.strftime('%d %b %Y')})"

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




































































