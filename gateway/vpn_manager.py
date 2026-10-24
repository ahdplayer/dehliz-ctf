#!/usr/bin/env python3
"""
Dehliz CTF WireGuard Dinamik Peer & İzolasyon Yöneticisi (API)
=============================================================
CTFd'nin arka planda çağırarak her takım ve oyuncu için dinamik
WireGuard profili üretmesini ve iptables kurallarını yönetmesini sağlar.
"""

import os
import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

WG_DIR = "/etc/wireguard"
PEERS_DB = os.path.join(WG_DIR, "peers.json")
HOSTS_FILE = os.path.join(WG_DIR, "hosts")
LISTEN_PORT = 5000

WG_HOST = os.environ.get("WG_HOST", "127.0.0.1")
WG_PORT = os.environ.get("WG_PORT", "51820")
WG_DNS = os.environ.get("WG_DNS", "10.13.37.1")
DEHLIZ_DOMAIN = os.environ.get("DEHLIZ_DOMAIN", "dehliz.local")


def load_dns_records():
    records = {}
    if os.path.exists(HOSTS_FILE):
        with open(HOSTS_FILE, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    records[parts[1]] = parts[0]
    return records


def add_dns_record(domain, ip):
    records = load_dns_records()
    records[domain] = ip
    with open(HOSTS_FILE, "w") as f:
        for d, i in records.items():
            f.write(f"{i} {d}\n")
    subprocess.run(["pkill", "-HUP", "dnsmasq"], check=False)
    return records


def load_peers():
    if os.path.exists(PEERS_DB):
        try:
            with open(PEERS_DB, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_peers(peers):
    with open(PEERS_DB, "w") as f:
        json.dump(peers, f, indent=2)


def get_server_pubkey():
    pub_file = os.path.join(WG_DIR, "server.pub")
    if os.path.exists(pub_file):
        with open(pub_file, "r") as f:
            return f.read().strip()
    return ""


def apply_team_firewall(team_id):
    """Takım için iptables mikro-bölümleme kurallarını dinamik olarak ekler."""
    team_net = f"10.10.{team_id}.0/24"
    team_vpn = f"10.13.{team_id}.0/24"

    commands = [
        # 1. Takım oyuncuları CTFd Canlı Soru Havuzuna (10.0.0.0/16 - Tüm Docker Swarm Subnetleri) erişebilir:
        f"iptables -C FORWARD -i wg0 -s {team_vpn} -d 10.0.0.0/16 -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i wg0 -s {team_vpn} -d 10.0.0.0/16 -j ACCEPT",
        # 2. Takım oyuncuları KENDİ ÖZEL LABLARINA (10.10.T.0/24) erişebilir:
        f"iptables -C FORWARD -i wg0 -s {team_vpn} -d {team_net} -j ACCEPT 2>/dev/null || iptables -I FORWARD 2 -i wg0 -s {team_vpn} -d {team_net} -j ACCEPT",
        # 3. Takım oyuncuları BİRBİRLERİNE erişebilir (Takım içi işbirliği):
        f"iptables -C FORWARD -i wg0 -s {team_vpn} -d {team_vpn} -j ACCEPT 2>/dev/null || iptables -I FORWARD 3 -i wg0 -s {team_vpn} -d {team_vpn} -j ACCEPT",
        # 4. Takım oyuncuları başka hiçbir yere gidemez (İzolasyon - DROP):
        f"iptables -C FORWARD -i wg0 -s {team_vpn} -j DROP 2>/dev/null || iptables -A FORWARD -i wg0 -s {team_vpn} -j DROP"
    ]

    for cmd in commands:
        subprocess.run(cmd, shell=True, check=False)


def restore_existing_peers():
    """Kayıtlı peer'ları başlangıçta WireGuard çekirdeğine geri yükler."""
    peers = load_peers()
    print(f"[*] Kayıtlı {len(peers)} adet peer yeniden yükleniyor...")
    for peer_key, data in peers.items():
        try:
            pub_key = data["public_key"]
            ip = data["ip"]
            team_id = data["team_id"]
            subprocess.run([
                "wg", "set", "wg0",
                "peer", pub_key,
                "allowed-ips", f"{ip}/32"
            ], check=False)
            apply_team_firewall(team_id)
        except Exception as e:
            print(f"[!] Peer yükleme hatası ({peer_key}): {e}")


def register_peer(team_id, user_id, username="player"):
    peers = load_peers()
    peer_key = f"{team_id}_{user_id}"

    # Kullanıcı zaten kayıtlıysa mevcut configi döndür
    if peer_key in peers:
        record = peers[peer_key]
        if "10.0.0.0/16" not in record.get("config", ""):
            server_pub = get_server_pubkey()
            priv = record.get("private_key", "")
            record["config"] = f"""[Interface]
PrivateKey = {priv}
Address = {record['ip']}/24
DNS = {WG_DNS}

[Peer]
PublicKey = {server_pub}
Endpoint = {WG_HOST}:{WG_PORT}
AllowedIPs = 10.13.{team_id}.0/24, 10.0.0.0/16, 10.10.{team_id}.0/24, {WG_DNS}/32
PersistentKeepalive = 25
"""
            peers[peer_key] = record
            save_peers(peers)
        return record

    # 1. WireGuard Anahtar Çifti Üret
    priv_run = subprocess.run(["wg", "genkey"], stdout=subprocess.PIPE, text=True, check=True)
    priv_key = priv_run.stdout.strip()
    pub_run = subprocess.run(["wg", "pubkey"], input=priv_key, stdout=subprocess.PIPE, text=True, check=True)
    pub_key = pub_run.stdout.strip()

    # 2. IP Belirle: 10.13.<team_id>.<user_id> (user_id mod 250 + 2 if user_id > 254)
    ip_last_octet = (user_id % 250) + 2 if user_id > 254 else user_id
    assigned_ip = f"10.13.{team_id}.{ip_last_octet}"

    # 3. Canlı WireGuard Arayüzüne Ekle (Sıfır Kesinti!)
    subprocess.run([
        "wg", "set", "wg0",
        "peer", pub_key,
        "allowed-ips", f"{assigned_ip}/32"
    ], check=True)

    # 4. Takım Güvenlik Duvarı Kurallarını Güncelle
    apply_team_firewall(team_id)

    # 5. İstemci .conf Metnini Oluştur
    server_pub = get_server_pubkey()
    config_content = f"""[Interface]
PrivateKey = {priv_key}
Address = {assigned_ip}/24
DNS = {WG_DNS}

[Peer]
PublicKey = {server_pub}
Endpoint = {WG_HOST}:{WG_PORT}
AllowedIPs = 10.13.{team_id}.0/24, 10.0.0.0/16, 10.10.{team_id}.0/24, {WG_DNS}/32
PersistentKeepalive = 25
"""

    record = {
        "team_id": team_id,
        "user_id": user_id,
        "username": username,
        "ip": assigned_ip,
        "public_key": pub_key,
        "private_key": priv_key,
        "config": config_content
    }

    peers[peer_key] = record
    save_peers(peers)
    return record


class APIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        
        if url.path == "/health":
            self._send_json({"status": "ok", "service": "dehliz-vpn-manager"})
        elif url.path == "/api/status":
            try:
                res = subprocess.run(["wg", "show", "wg0", "dump"], stdout=subprocess.PIPE, text=True)
                lines = res.stdout.strip().splitlines()
                peers = load_peers()
                dns_records = load_dns_records()
                self._send_json({
                    "status": "online",
                    "total_registered_peers": len(peers),
                    "active_wg_lines": len(lines),
                    "dns_records": dns_records,
                    "peers": peers
                })
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
        elif url.path.startswith("/api/peer/"):
            peer_key = url.path.replace("/api/peer/", "").strip()
            peers = load_peers()
            if peer_key in peers:
                self._send_json(peers[peer_key])
            else:
                self._send_json({"error": "Peer bulunamadi"}, status=404)
        else:
            self._send_json({"error": "Endpoint bulunamadi"}, status=404)

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len)

        try:
            req_data = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            self._send_json({"error": "Gecersiz JSON"}, status=400)
            return

        if url.path == "/api/peer":
            team_id = req_data.get("team_id")
            user_id = req_data.get("user_id")
            username = req_data.get("username", "player")

            if team_id is None or user_id is None:
                self._send_json({"error": "team_id ve user_id zorunludur"}, status=400)
                return

            try:
                peer_record = register_peer(int(team_id), int(user_id), username)
                self._send_json(peer_record, status=201)
            except Exception as e:
                self._send_json({"error": f"Peer kayit hatasi: {str(e)}"}, status=500)

        elif url.path == "/api/dns":
            domain = req_data.get("domain")
            ip = req_data.get("ip")
            if not domain or not ip:
                self._send_json({"error": "domain ve ip zorunludur"}, status=400)
                return
            try:
                records = add_dns_record(domain, ip)
                self._send_json({"status": "ok", "records": records}, status=201)
            except Exception as e:
                self._send_json({"error": f"DNS kayit hatasi: {str(e)}"}, status=500)
        else:
            self._send_json({"error": "Endpoint bulunamadi"}, status=404)

    def log_message(self, format, *args):
        # Sade standart erişim logu
        print(f"[{self.log_date_time_string()}] {self.address_string()} - {format % args}")


def run_server():
    restore_existing_peers()
    server_address = ("", LISTEN_PORT)
    httpd = HTTPServer(server_address, APIHandler)
    print(f"[*] Dehliz VPN Manager API {LISTEN_PORT} portunda dinliyor...")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
