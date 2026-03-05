import requests
import json
import os
import shutil

# 1. Geser data H-1 menjadi H-2
if os.path.exists('data_h1.json'):
    shutil.copy('data_h1.json', 'data_h2.json')
    print("Sukses geser H-1 ke H-2")

# 2. Ambil Kredensial dari Brankas GitHub Secrets (Bukan st.secrets lagi)
akun_list = [
    {"username": os.environ.get("AWSCENTER_USER"), "password": os.environ.get("AWSCENTER_PASS")},
    {"username": os.environ.get("AWSCENTER_USER2"), "password": os.environ.get("AWSCENTER_PASS2")}
]

login_url = "https://awscenter.bmkg.go.id/base/verify"
api_url = "https://awscenter.bmkg.go.id/dashboard/get_parameter_terkini_hujan"
kota_ntb = ['Kota Mataram', 'Kab. Lombok Barat', 'Kab. Lombok Tengah', 'Kab. Lombok Timur', 'Kab. Lombok Utara', 'Kab. Sumbawa Barat', 'Kab. Sumbawa', 'Kab. Dompu', 'Kab. Bima', 'Kota Bima']

data_tersimpan = []

# 3. Proses Login dan Tarik Data (Niru gaya kodingan lu bro!)
for akun in akun_list:
    if not akun["username"]: 
        continue # Skip kalau akun kosong
        
    session = requests.Session()
    try:
        # Aksi 1: Dobrak masuk (Login)
        session.post(login_url, data=akun)
        
        # Aksi 2: Sedot datanya
        req = session.get(api_url)
        data_mentah = req.json()
        
        # Aksi 3: Saring khusus NTB aja biar file json-nya gak bengkak
        for item in data_mentah:
            if item.get('nama_kota') in kota_ntb:
                data_tersimpan.append(item)
                
        print(f"Sukses narik pakai akun: {akun['username']}")
        
    except Exception as e:
        print(f"Gagal pakai akun {akun['username']}: {e}")

# 4. Save jadi file JSON H-1
if data_tersimpan:
    with open('data_h1.json', 'w') as f:
        json.dump(data_tersimpan, f)
    print("Mantap! File data_h1.json udah dibikin secara fisik.")
else:
    print("Gagal narik / Data NTB kosong Bro.")
