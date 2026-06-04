import socket
import time
import argparse
import csv
import os
from datetime import datetime

# ============================================================
# FUNGSI KLIEN TCP (Tetap ada jika butuh tes manual via CMD)
# ============================================================
def run_tcp(host, port, path):
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_sock.connect((host, port))
        request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        client_sock.sendall(request.encode())
        
        print(f"--- Menerima balasan dari {host}:{port} ---\n")
        response = b""
        while True:
            data = client_sock.recv(4096)
            if not data:
                break
            response += data
        
        # Cetak isi respons
        print(response.decode(errors='ignore'))
    except Exception as e:
        print(f"[ERROR] Koneksi TCP gagal: {e}")
    finally:
        client_sock.close()

# ============================================================
# FUNGSI KLIEN UDP (Untuk Tes QoS)
# ============================================================
def run_udp(host, port):
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_sock.settimeout(1.0) # Waktu tunggu maksimal 1 detik per paket
    
    sent = 10
    received = 0
    rtts = []
    
    print(f"Memulai Ping UDP ke {host} di port {port}...\n")
    
    for i in range(1, sent + 1):
        try:
            waktu_kirim = time.time()
            pesan = f"Ping {i} {waktu_kirim}"
            client_sock.sendto(pesan.encode(), (host, port))
            
            data, addr = client_sock.recvfrom(1024)
            waktu_terima = time.time()
            
            rtt = (waktu_terima - waktu_kirim) * 1000 # Ubah ke milidetik
            rtts.append(rtt)
            received += 1
            
            print(f"Balasan dari {addr[0]}: seq={i} waktu={rtt:.2f}ms")
        except socket.timeout:
            print(f"Request timed out (seq={i})")
        except ConnectionResetError:
            print(f"Koneksi terputus / Server Mati (seq={i})")
        
        time.sleep(0.1) # Jeda sedikit antar ping agar tidak bertumpuk
        
    # ============================================================
    # PERHITUNGAN STATISTIK QoS
    # ============================================================
    loss = ((sent - received) / sent) * 100
    
    if received > 0:
        min_rtt = min(rtts)
        max_rtt = max(rtts)
        avg_rtt = sum(rtts) / len(rtts)
        
        # Hitung Jitter (Selisih waktu antar paket yang berurutan)
        jitters = []
        for i in range(1, len(rtts)):
            jitters.append(abs(rtts[i] - rtts[i-1]))
        jitter_avg = sum(jitters) / len(jitters) if len(jitters) > 0 else 0.0
    else:
        min_rtt = max_rtt = avg_rtt = jitter_avg = 0.0
        
    print("\n--- Statistik UDP Ping ---")
    print(f"Paket: Dikirim = {sent}, Diterima = {received}, Hilang = {sent - received} ({loss:.1f}% loss)")
    if received > 0:
        print(f"RTT    : Min = {min_rtt:.2f}ms, Max = {max_rtt:.2f}ms, Rata-rata = {avg_rtt:.2f}ms")
        print(f"Jitter : {jitter_avg:.2f}ms")
        
    # Panggil fungsi untuk menyimpan ke Excel/CSV
    simpan_ke_csv(host, sent, received, loss, min_rtt, max_rtt, avg_rtt, jitter_avg)

# ============================================================
# FUNGSI MENYIMPAN KE CSV
# ============================================================
def simpan_ke_csv(host, sent, received, loss, min_rtt, max_rtt, avg_rtt, jitter):
    nama_file = "qos_log.csv"
    file_baru = not os.path.exists(nama_file) # Cek apakah file sudah ada
    waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(nama_file, mode='a', newline='') as f:
        writer = csv.writer(f)
        
        # Buat judul kolom di baris pertama jika filenya baru dibuat
        if file_baru:
            writer.writerow(["Waktu_Pengujian", "Target_IP", "Dikirim", "Diterima", "Loss(%)", "Min_RTT(ms)", "Max_RTT(ms)", "Avg_RTT(ms)", "Jitter(ms)"])
        
        # Tulis data hasil tes di baris bawahnya
        writer.writerow([waktu_sekarang, host, sent, received, round(loss, 2), round(min_rtt, 2), round(max_rtt, 2), round(avg_rtt, 2), round(jitter, 2)])
        
    print(f"\n[+] Sukses! Hasil uji QoS berhasil disimpan ke dalam file '{nama_file}'")

# ============================================================
# TITIK JALAN PROGRAM UTAMA
# ============================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Klien Pengujian Jaringan")
    parser.add_argument('--mode', choices=['tcp', 'udp'], required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--path', default='/index.html')
    
    args = parser.parse_args()
    
    if args.mode == 'tcp':
        run_tcp(args.host, args.port, args.path)
    else:
        run_udp(args.host, args.port)