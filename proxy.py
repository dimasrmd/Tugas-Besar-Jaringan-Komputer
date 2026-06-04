import socket
import threading
import os
import time
from datetime import datetime

# Gembok untuk mencegah tabrakan saat menulis file cache (Race Condition)
cache_lock = threading.Lock()

# Konfigurasi Proxy
PROXY_HOST = '0.0.0.0'
PROXY_PORT = 8080


# ============================================================
# # Konfigurasi Web Server (Milik Abi)
# SERVER_HOST = '10.22.75.217'
# SERVER_PORT = 8000

# Konfigurasi Web Server (Sementara untuk tes lokal)
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 8000
# ============================================================

# Konfigurasi Direktori Cache
CACHE_DIR = "cache"

# Buat folder 'cache' secara otomatis jika belum ada
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# ============================================================
# FUNGSI MEMBACA FILE ERROR HTML
# ============================================================
def load_error_html(kode_error):
    """Mencoba membaca file HTML darurat, jika gagal pakai teks biasa."""
    try:
        with open(f"status/{kode_error}.html", "rb") as f:
            return f.read()
    except:
        return f"<h1>{kode_error} Error</h1><p>File status/{kode_error}.html hilang.</p>".encode()


def handle_client(client_socket, client_address):
    """Menangani setiap client di thread yang terpisah"""
    try:
        # Terima request HTTP dari client (Ariel/Browser)
        request = client_socket.recv(4096)
        if not request:
            return
            
        # Parse URL dari HTTP request
        request_text = request.decode('utf-8', errors='ignore')
        baris_pertama = request_text.split('\n')[0]
        
        path_url = "Unknown"
        if len(baris_pertama.split()) > 1:
            path_url = baris_pertama.split()[1]

        # Setup logging dasar dan stopwatch
        waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        waktu_mulai = time.time()

        # Mengubah nama path URL menjadi nama file yang aman (mendukung folder seperti /css/style.css)
        nama_file_cache = path_url.replace("/", "_")
        if nama_file_cache == "_" or nama_file_cache == "": 
            nama_file_cache = "_index.html"
            
        lokasi_cache = os.path.join(CACHE_DIR, nama_file_cache)

        # CEK CACHE: Apakah filenya sudah ada di dalam folder?
        if os.path.exists(lokasi_cache):
            # ===== SKENARIO CACHE HIT =====
            with open(lokasi_cache, "rb") as f:
                data_cache = f.read()
                client_socket.sendall(data_cache)
                
            durasi = (time.time() - waktu_mulai) * 1000
            print(f"[{waktu_sekarang}] {client_address[0]} {path_url} status=HIT response_time={durasi:.2f}ms")

        else:
            # ===== SKENARIO CACHE MISS =====
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.settimeout(5.0) # Batas tunggu server 5 detik
            try:
                server_socket.connect((SERVER_HOST, SERVER_PORT))
                server_socket.sendall(request)

                full_response = b""
                while True:
                    response = server_socket.recv(4096)
                    if len(response) > 0:
                        # VALIDASI 502: Pastikan data diawali dengan "HTTP/"
                        if not full_response and not response.startswith(b"HTTP/"):
                            raise ValueError("Balasan Server Korup / Bukan HTTP")
                        
                        client_socket.sendall(response)
                        full_response += response
                    else:
                        break
                
                # Simpan ke folder cache dengan pengamanan gembok (Lock)
                if full_response:
                    try:
                        with cache_lock:
                            with open(lokasi_cache, "wb") as f:
                                f.write(full_response)
                    except Exception as e:
                        print(f"[WARNING] Gagal menyimpan cache: {e}")
                
                durasi = (time.time() - waktu_mulai) * 1000
                print(f"[{waktu_sekarang}] {client_address[0]} {path_url} status=MISS response_time={durasi:.2f}ms")
            
            except ConnectionRefusedError:
                body = load_error_html(504)
                header = (
                    "HTTP/1.1 504 Gateway Timeout\r\n"
                    "Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
                client_socket.sendall(header + body)
                durasi = (time.time() - waktu_mulai) * 1000
                print(f"[{waktu_sekarang}] {client_address[0]} {path_url} status=504_GATEWAY_TIMEOUT response_time={durasi:.2f}ms")
                
            except TimeoutError: 
                body = load_error_html(504)
                header = (
                    "HTTP/1.1 504 Gateway Timeout\r\n"
                    "Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
                client_socket.sendall(header + body)
                durasi = (time.time() - waktu_mulai) * 1000
                print(f"[{waktu_sekarang}] {client_address[0]} {path_url} status=504_TIMEOUT response_time={durasi:.2f}ms")
                
            except Exception as e:
                body = load_error_html(502)
                header = (
                    "HTTP/1.1 502 Bad Gateway\r\n"
                    "Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
                client_socket.sendall(header + body)
                durasi = (time.time() - waktu_mulai) * 1000
                print(f"[{waktu_sekarang}] {client_address[0]} {path_url} status=502_BAD_GATEWAY response_time={durasi:.2f}ms")
                
            finally:
                server_socket.close()
        
    except Exception as e:
        print(f"[ERROR] Masalah pada client: {e}")
    finally:
        client_socket.close()

def start_proxy():
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy_socket.bind((PROXY_HOST, PROXY_PORT))
    proxy_socket.listen(10)
    proxy_socket.settimeout(1.0) 
    
    print(f"[*] Proxy Server aktif dan mendengarkan di port {PROXY_PORT}...")
    
    try:
        while True:
            try:
                client_socket, client_address = proxy_socket.accept()
                client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
                client_thread.daemon = True 
                client_thread.start()
            except TimeoutError:
                continue
            
    except KeyboardInterrupt:
        print("\n[*] Mematikan Proxy Server...")
    finally:
        proxy_socket.close()

if __name__ == "__main__":
    start_proxy()