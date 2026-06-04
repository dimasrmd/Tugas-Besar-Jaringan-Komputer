import socket
import os
import threading
from datetime import datetime

# ============================================================
# KONFIGURASI
# ============================================================
HOST     = '0.0.0.0'
PORT_TCP = 8000
PORT_UDP = 9000

# ============================================================
# LOGGING HELPER
# ============================================================
def log(protocol, status, info, client_ip="-"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{protocol}] [{status}] IP:{client_ip} | {info}")

# ============================================================
# FUNGSI DETEKSI TIPE FILE (MIME TYPE) UNTUK CHROME
# ============================================================
def get_content_type(filepath):
    if filepath.endswith('.css'):
        return 'text/css'
    elif filepath.endswith('.png'):
        return 'image/png'
    elif filepath.endswith('.jpg') or filepath.endswith('.jpeg'):
        return 'image/jpeg'
    elif filepath.endswith('.mp4'):
        return 'video/mp4'
    elif filepath.endswith('.js'):
        return 'application/javascript'
    else:
        return 'text/html; charset=utf-8'

# ============================================================
# TCP - HANDLE CLIENT (dijalankan di thread terpisah)
# ============================================================
def handle_client(conn, addr):
    client_ip = addr[0]
    log("TCP", "CONNECT", f"Koneksi masuk dari {addr}")

    try:
        # Terima raw HTTP request
        data = conn.recv(4096)
        if not data:
            log("TCP", "EMPTY", "Data kosong, koneksi ditutup", client_ip)
            return

        # ── Parse HTTP request ──────────────────────────────
        request    = data.decode(errors='ignore')
        first_line = request.split('\r\n')[0]
        parts      = first_line.split(' ')

        # Validasi format request
        if len(parts) < 2:
            log("TCP", "BAD_REQ", f"Request tidak valid: {first_line}", client_ip)
            return

        method = parts[0]   # GET
        path   = parts[1]   # /index.html atau /css/style.css

        log("TCP", "REQUEST", f"{method} {path}", client_ip)

        # Default path ke index.html jika hanya mengetikkan "/"
        if path == '/':
            path = '/index.html'

        # Hilangkan slash di depan agar bisa dibaca sebagai path Windows yang benar
        filename = path.lstrip('/')

        # Pemicu Error 500 buatan
        if filename == 'error.html':
            raise RuntimeError("Simulasi 500 error")

        # ── Baca file & kirim response ──────────────────────
        if os.path.exists(filename) and os.path.isfile(filename):
            try:
                with open(filename, 'rb') as f:
                    content = f.read()

                # Dapatkan label tipe file yang benar (Penting untuk Chrome)
                tipe_file = get_content_type(filename)

                header = (
                    # "RUSAK/1.1 200 OK\r\n" # Ini untuk test 502 Error
                    "HTTP/1.1 200 OK\r\n"
                    f"Content-Type: {tipe_file}\r\n"
                    f"Content-Length: {len(content)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                )
                conn.sendall(header.encode() + content)
                log("TCP", "200 OK", f"File served: {filename}", client_ip)

            except Exception as read_err:
                # File ada tapi gagal dibaca → 500
                raise RuntimeError(f"Gagal baca file: {read_err}")

        else:
            # ── SKENARIO 404 NOT FOUND ──
            try:
                # Coba baca file 404 buatan kalian
                with open('status/404.html', 'rb') as f:
                    body = f.read()
            except:
                # Jika file status/404.html tidak ditemukan, pakai teks biasa
                body = b"<h1>404 Not Found</h1><p>File status/404.html hilang.</p>"
            
            header = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            conn.sendall(header.encode() + body)
            log("TCP", "404", f"File tidak ada: {filename}", client_ip)

    except Exception as e:
        # ── SKENARIO 500 INTERNAL SERVER ERROR ──
        log("TCP", "500 ERROR", f"Exception: {e}", client_ip)
        
        try:
            # Coba baca file 500 buatan kalian
            with open('status/500.html', 'rb') as f:
                body = f.read()
        except:
            body = b"<h1>500 Internal Server Error</h1>"
            
        header = (
            "HTTP/1.1 500 Internal Server Error\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        try:
            conn.sendall(header.encode() + body)
        except:
            pass  # kalau send juga gagal, skip saja

    finally:
        conn.close()  # SELALU tutup koneksi
        log("TCP", "CLOSE", f"Koneksi ditutup untuk {client_ip}", client_ip)

# ============================================================
# TCP SERVER — main loop, hanya accept + spawn thread
# ============================================================
def tcp_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT_TCP))
    server_sock.listen(10)
    log("TCP", "START", f"HTTP Server berjalan di port {PORT_TCP}")

    while True:
        conn, addr = server_sock.accept()
        t = threading.Thread(
            target=handle_client,
            args=(conn, addr),
            daemon=True
        )
        t.start()
        log("TCP", "THREAD", f"Thread baru spawned. Aktif: {threading.active_count() - 1}")

# ============================================================
# UDP SERVER — echo server untuk QoS testing
# ============================================================
def udp_server():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind((HOST, PORT_UDP))
    log("UDP", "START", f"UDP Echo Server berjalan di port {PORT_UDP}")

    while True:
        try:
            # Terima paket UDP
            # Format payload dari client: "Ping <seq> <timestamp>"
            data, addr = udp_sock.recvfrom(1024)

            log("UDP", "RECV", f"Paket dari {addr}: {data.decode(errors='ignore')}")

            # Echo balik — payload tidak diubah sama sekali
            udp_sock.sendto(data, addr)

            log("UDP", "ECHO", f"Paket dipantulkan ke {addr}")

        except Exception as e:
            log("UDP", "ERROR", f"Exception: {e}")

# ============================================================
# MAIN — jalankan TCP dan UDP bersamaan
# ============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  WEBSERVER.PY - Tubes Jaringan Komputer")
    print("=" * 55)

    # UDP jalan di thread terpisah
    udp_thread = threading.Thread(
        target=udp_server,
        daemon=True
    )
    udp_thread.start()

    # TCP jalan di main thread
    # (kalau tcp_server() crash, program berhenti — ini wajar)
    tcp_server()