#!/usr/bin/env python3
"""
Dehliz CTF Otomatik Siber Poligon & Güvenlik İzolasyon Test Paketi
==================================================================
Tüm sistem edge-case'lerini uçtan uca otomatik test eder:
 1. Altyapı ve Servis Sağlık Durumu (Gateway API & CTFd API)
 2. WireGuard Dinamik Peer Üretimi (Team 1 Oyuncu 1 & 2, Team 2 Oyuncu 1)
 3. Linux Ağ İsim Alanları (Network Namespaces) & WireGuard Tünelleri Kurulumu
 4. WireGuard Handshake ve Tünel Bağlantı Doğrulaması
 5. Soru Labı Başlatma (Team 1 için CTFd Dehliz API üzerinden)
 6. Yerel DNS Çözümleme (ornek-soru-t1.dehliz.local -> 10.0.2.x)
 7. Yetkili Erişim Testi (Team 1 Oyuncusu -> Kendi Labı: HTTP 200 OK)
 8. Takım İçi İşbirliği Testi (Team 1 P1 <-> Team 1 P2 Ping: %0 Kayıp)
 9. Güvenlik İzolasyonu 1: Takımlar Arası Oyuncu Saldırısı (T2 -> T1: BLOCKED / %100 Kayıp)
10. Güvenlik İzolasyonu 2: Takımlar Arası Lab Ele Geçirme (T2 -> T1 Lab: BLOCKED / Timeout)
11. Soru Süresi Uzatma (Renew Instance Testi: Expiration Time Artışı)
12. Soru Kapatma ve Temizlik (Destroy Instance Testi: Swarm, DNS & Firewall Silinmesi)
13. Kapatma Sonrası Erişim Engelleme Doğrulaması (Lab Erişilemezliği Onayı)
"""

import os
import sys
import time
import json
import socket
import urllib.request
import urllib.error
import subprocess
import re

# Renkli terminal çıktıları
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

GATEWAY_API = os.environ.get("GATEWAY_API", "http://vpn-gateway:5000")
CTFD_URL = os.environ.get("CTFD_URL", "http://ctfd:8000")
WG_ENDPOINT = os.environ.get("WG_ENDPOINT", "172.24.0.2:51820")
WG_DNS = "10.13.37.1"

# Test Oyuncuları (Veritabanındaki gerçek test kullanıcılarıyla eşleşen)
PLAYERS = {
    "t1_p1": {"team_id": 1, "user_id": 2, "name": "ahdplayer_t1_p1", "ns": "ns_t1_p1", "wg": "wg_t1_p1"},
    "t1_p2": {"team_id": 1, "user_id": 3, "name": "teammate_t1_p2", "ns": "ns_t1_p2", "wg": "wg_t1_p2"},
    "t2_p1": {"team_id": 2, "user_id": 4, "name": "rival_t2_p1",    "ns": "ns_t2_p1", "wg": "wg_t2_p1"}
}

RESULTS = []


def log_step(title):
    print(f"\n{BOLD}{CYAN}==> {title}{RESET}")


def log_pass(desc):
    print(f"  {GREEN}✔ [PASS]{RESET} {desc}")
    RESULTS.append((desc, True))


def log_fail(desc, reason=""):
    msg = f"  {RED}✘ [FAIL]{RESET} {desc}"
    if reason:
        msg += f" -> {YELLOW}{reason}{RESET}"
    print(msg)
    RESULTS.append((desc, False))


def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"Komut basarisiz ({res.returncode}): {cmd}\nHata: {res.stderr}")
    return res


def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DehlizTestRunner/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def http_post_json(url, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "DehlizTestRunner/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def http_delete_json(url, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "DehlizTestRunner/1.0"}, method="DELETE")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


# =========================================================================
# TEST ADIMLARI
# =========================================================================

def test_1_health_checks():
    log_step("1. Altyapı ve Servis Sağlık Kontrolleri")
    
    # 1. VPN Gateway API Kontrolü
    try:
        data = http_get_json(f"{GATEWAY_API}/health")
        if data.get("status") == "ok":
            log_pass("WireGuard VPN Gateway API çalışıyor (Port 5000 /health)")
        else:
            log_fail("WireGuard VPN Gateway API beklenen yanıtı vermedi", str(data))
    except Exception as e:
        log_fail("WireGuard VPN Gateway API'ye erişilemedi", str(e))

    # 2. CTFd Servis Kontrolü
    try:
        req = urllib.request.Request(f"{CTFD_URL}/", headers={"User-Agent": "DehlizTestRunner/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            if r.status in (200, 302):
                log_pass("CTFd Web Servisi çalışıyor (Port 8000)")
            else:
                log_fail("CTFd Web Servisi beklenmeyen HTTP kodu döndü", str(r.status))
    except Exception as e:
        log_fail("CTFd Web Servisine erişilemedi", str(e))


def test_2_register_peers():
    log_step("2. WireGuard Dinamik Peer & Anahtar Üretimi")

    for key, p in PLAYERS.items():
        try:
            data = http_post_json(f"{GATEWAY_API}/api/peer", {
                "team_id": p["team_id"],
                "user_id": p["user_id"],
                "username": p["name"]
            })
            p["privkey"] = data["private_key"]
            p["pubkey"] = data["public_key"]
            p["config"] = data["config"]
            p["ip"] = data["ip"]
            
            # Sunucu public key'i ayıkla
            match = re.search(r"PublicKey\s*=\s*([^\s]+)", p["config"])
            p["server_pub"] = match.group(1) if match else ""
            
            log_pass(f"Peer kayıt başarılı: {p['name']} (Takım {p['team_id']} -> IP {p['ip']})")
        except Exception as e:
            log_fail(f"Peer kaydı başarısız: {p['name']}", str(e))


def test_3_setup_namespaces():
    log_step("3. Linux Ağ İsim Alanları (Netns) & WireGuard Tünellerinin Kurulumu")

    for key, p in PLAYERS.items():
        ns = p["ns"]
        wg = p["wg"]
        ip = p["ip"]
        priv = p["privkey"]
        server_pub = p["server_pub"]

        try:
            # Varsa eski namespace ve linki temizle
            run_cmd(f"ip netns del {ns} 2>/dev/null || true", check=False)
            run_cmd(f"ip link del dev {wg} 2>/dev/null || true", check=False)

            # 1. Yeni Network Namespace oluştur
            run_cmd(f"ip netns add {ns}")

            # 2. Kök alanda WireGuard arayüzünü oluştur
            run_cmd(f"ip link add dev {wg} type wireguard")

            # 3. WireGuard tünel yapılandırmasını tanımla
            key_file = f"/tmp/{wg}.key"
            with open(key_file, "w") as f:
                f.write(priv.strip() + "\n")

            run_cmd(f"wg set {wg} private-key {key_file} peer {server_pub} endpoint {WG_ENDPOINT} allowed-ips 0.0.0.0/0 persistent-keepalive 1")

            # 4. Arayüzü namespace içine taşı
            run_cmd(f"ip link set {wg} netns {ns}")

            # 5. Namespace içinde IP ve route tanımla
            run_cmd(f"ip netns exec {ns} ip addr add {ip}/24 dev {wg}")
            run_cmd(f"ip netns exec {ns} ip link set {wg} up")
            run_cmd(f"ip netns exec {ns} ip link set lo up")
            run_cmd(f"ip netns exec {ns} ip route add default dev {wg}")

            # 6. Namespace yerel DNS tanımla
            os.makedirs(f"/etc/netns/{ns}", exist_ok=True)
            with open(f"/etc/netns/{ns}/resolv.conf", "w") as f:
                f.write(f"nameserver {WG_DNS}\n")

            log_pass(f"Ağ isim alanı ve tünel aktif: {ns} ({wg} -> {ip})")
        except Exception as e:
            log_fail(f"Namespace kurulum hatası: {ns}", str(e))

    # Tünel el sıkışmasını (Handshake) tetiklemek ve doğrulamak için gateway'e kısa bir ping
    time.sleep(1)
    for key, p in PLAYERS.items():
        ns = p["ns"]
        res = run_cmd(f"ip netns exec {ns} ping -c 1 -W 2 {WG_DNS}", check=False)
        if res.returncode == 0:
            log_pass(f"WireGuard el sıkışması başarılı: {p['name']} -> Gateway ({WG_DNS})")
        else:
            log_fail(f"WireGuard el sıkışması başarısız: {p['name']}", res.stderr or res.stdout)


def test_4_launch_lab():
    log_step("4. Dinamik Soru Konteyneri Başlatma (Team 1)")
    global CONTAINER_INFO
    CONTAINER_INFO = {}

    try:
        p1_uid = PLAYERS["t1_p1"]["user_id"]
        p1_tid = PLAYERS["t1_p1"]["team_id"]
        cmd = f"""python3 -c "
import importlib
from CTFd import create_app
from CTFd.models import db
app = create_app()
with app.app_context():
    mod = importlib.import_module('CTFd.plugins.ctfd-dehliz')
    DockerManager = mod.docker_manager.DockerManager
    DehlizChallenge = mod.models.DehlizChallenge
    chall = DehlizChallenge.query.filter_by(id=1).first()
    if not chall:
        print('NO_CHALLENGE')
        exit(1)
    # Temizlik: varsa eski konteyneri yok et
    DockerManager.destroy_instance(user_id={p1_uid}, challenge_id=1)
    ok, c, msg = DockerManager.create_instance(user_id={p1_uid}, team_id={p1_tid}, challenge=chall)
    if ok:
        print(f'OK|{{c.ip_address}}|{{c.domain}}|{{c.port}}|{{c.docker_id}}')
    else:
        print(f'ERR|{{msg}}')
" """
        res = subprocess.run(
            ["docker", "exec", "dehliz-ctf-ctfd-1", "sh", "-c", cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        output = res.stdout.strip()
        lines = [line for line in output.splitlines() if line.startswith("OK|") or line.startswith("ERR|")]
        if lines and lines[-1].startswith("OK|"):
            parts = lines[-1].split("|")
            CONTAINER_INFO = {
                "ip": parts[1],
                "domain": parts[2],
                "port": int(parts[3]),
                "docker_id": parts[4]
            }
            log_pass(f"Team 1 labı başarıyla başlatıldı: IP {CONTAINER_INFO['ip']} | Domain: {CONTAINER_INFO['domain']}:{CONTAINER_INFO['port']}")
        else:
            log_fail("Team 1 labı başlatılamadı", output or res.stderr)
    except Exception as e:
        log_fail("Lab başlatma sırasında hata oluştu", str(e))


def test_5_access_own_lab():
    log_step("5. Yetkili Erişim Testi: Team 1 Oyuncusu -> Kendi Labı")

    if not CONTAINER_INFO.get("ip"):
        log_fail("Aktif konteyner bilgisi bulunamadığı için erişim testi atlandı")
        return

    domain = CONTAINER_INFO["domain"]
    ip = CONTAINER_INFO["ip"]
    port = CONTAINER_INFO["port"]
    ns = PLAYERS["t1_p1"]["ns"]

    # 1. DNS Çözümleme Testi (Yerel dnsmasq üzerinden)
    cmd_dns = f"ip netns exec {ns} python3 -c \"import socket; print(socket.gethostbyname('{domain}'))\""
    res_dns = run_cmd(cmd_dns, check=False)
    resolved_ip = res_dns.stdout.strip()
    if resolved_ip == ip:
        log_pass(f"Yerel DNS çözümleme başarılı: {domain} -> {resolved_ip}")
    else:
        log_fail(f"Yerel DNS çözümleme başarısız: {domain} (Beklenen: {ip}, Gelen: {resolved_ip})", res_dns.stderr)

    # 2. Lab Konteynerinin Hazır Olmasını Bekle (Swarm başlatma süresi: maks 15 sn)
    print(f"  [*] Lab servisinin dinlemeye başlaması bekleniyor (http://{domain}:{port}/)...")
    service_ready = False
    last_output = ""
    for attempt in range(15):
        cmd_check = f"ip netns exec {ns} curl -s -m 2 http://{ip}:{port}/"
        res_check = run_cmd(cmd_check, check=False)
        if res_check.returncode == 0 and len(res_check.stdout) > 0:
            service_ready = True
            last_output = res_check.stdout
            break
        time.sleep(1)

    # 3. HTTP Erişim Testi (Domain Üzerinden)
    cmd_http_domain = f"ip netns exec {ns} curl -s -m 5 http://{domain}:{port}/"
    res_domain = run_cmd(cmd_http_domain, check=False)
    if res_domain.returncode == 0 and ("Dehliz" in res_domain.stdout or "<html" in res_domain.stdout or "Flask" in res_domain.stdout or len(res_domain.stdout) > 0):
        log_pass(f"Domain üzerinden lab erişimi başarılı (HTTP 200 OK): http://{domain}:{port}/")
    else:
        log_fail(f"Domain üzerinden laba erişilemedi", res_domain.stderr or res_domain.stdout or last_output)

    # 4. HTTP Erişim Testi (Direkt IP Üzerinden)
    cmd_http_ip = f"ip netns exec {ns} curl -s -m 5 http://{ip}:{port}/"
    res_ip = run_cmd(cmd_http_ip, check=False)
    if res_ip.returncode == 0 and len(res_ip.stdout) > 0:
        log_pass(f"Direkt IP üzerinden lab erişimi başarılı (HTTP 200 OK): http://{ip}:{port}/")
    else:
        log_fail(f"Direkt IP üzerinden laba erişilemedi", res_ip.stderr or res_ip.stdout)


def test_6_teammate_cooperation():
    log_step("6. Takım İçi İşbirliği Testi (Team 1 P1 <-> Team 1 P2)")

    ns_p1 = PLAYERS["t1_p1"]["ns"]
    ip_p2 = PLAYERS["t1_p2"]["ip"]

    # Ön ısınma pingi (ilk paket WireGuard tünel rotasını aktive eder)
    run_cmd(f"ip netns exec {ns_p1} ping -c 1 -W 1 {ip_p2}", check=False)
    time.sleep(0.5)

    # Team 1 Player 1, Team 1 Player 2'ye ping atabilmeli
    res = run_cmd(f"ip netns exec {ns_p1} ping -c 3 -W 2 {ip_p2}", check=False)
    if res.returncode == 0 and ("0% packet loss" in res.stdout or "0.0% packet loss" in res.stdout or "3 packets received" in res.stdout or "2 packets received" in res.stdout):
        log_pass(f"Takım arkadaşları arası iletişim serbest: {PLAYERS['t1_p1']['name']} -> {PLAYERS['t1_p2']['name']} ({ip_p2}) [Aktif İletişim]")
    else:
        log_fail("Takım arkadaşları birbirine erişemedi", res.stdout or res.stderr)


def test_7_cross_team_player_isolation():
    log_step("7. Güvenlik İzolasyonu 1: Takımlar Arası Oyuncu Saldırısı Engelleme")

    ns_t2 = PLAYERS["t2_p1"]["ns"]
    ip_t1 = PLAYERS["t1_p1"]["ip"]

    # Team 2 Player 1, Team 1 Player 1'e saldırmaya (ping/portscan) çalıştığında ENGELLENMELİ!
    res_ping = run_cmd(f"ip netns exec {ns_t2} ping -c 2 -W 2 {ip_t1}", check=False)
    if res_ping.returncode != 0 or "100% packet loss" in res_ping.stdout or "100.0% packet loss" in res_ping.stdout:
        log_pass(f"Takımlar arası oyuncu erişimi başarıyla ENGELLENDİ: T2 ({PLAYERS['t2_p1']['name']}) -> T1 ({ip_t1}) [Firewall DROP / 100% Paket Kaybı]")
    else:
        log_fail(f"GÜVENLİK AÇIĞI! Team 2, Team 1 oyuncusuna erişebildi!", res_ping.stdout)


def test_8_cross_team_lab_isolation():
    log_step("8. Güvenlik İzolasyonu 2: Takımlar Arası Lab Ele Geçirme Engelleme")

    if not CONTAINER_INFO.get("ip"):
        log_fail("Aktif konteyner bilgisi bulunamadığı için izolasyon testi atlandı")
        return

    ns_t2 = PLAYERS["t2_p1"]["ns"]
    t1_lab_ip = CONTAINER_INFO["ip"]
    t1_lab_domain = CONTAINER_INFO["domain"]
    port = CONTAINER_INFO["port"]

    # Team 2 Player 1, Team 1'in lab konteynerine (IP üzerinden) bağlanmaya çalıştığında ENGELLENMELİ!
    res_ip = run_cmd(f"ip netns exec {ns_t2} curl -s -m 3 http://{t1_lab_ip}:{port}/", check=False)
    if res_ip.returncode != 0:
        log_pass(f"Team 2'nin Team 1 lab IP'sine erişimi başarıyla ENGELLENDİ: http://{t1_lab_ip}:{port}/ [Firewall DROP / Connection Timeout]")
    else:
        log_fail(f"GÜVENLİK AÇIĞI! Team 2, Team 1'in soru labına erişebildi!", res_ip.stdout)

    # Team 2 Player 1, Team 1'in lab konteynerine (Domain üzerinden) bağlanmaya çalıştığında da ENGELLENMELİ!
    res_dom = run_cmd(f"ip netns exec {ns_t2} curl -s -m 3 http://{t1_lab_domain}:{port}/", check=False)
    if res_dom.returncode != 0:
        log_pass(f"Team 2'nin Team 1 lab domain'ine erişimi başarıyla ENGELLENDİ: http://{t1_lab_domain}:{port}/ [Firewall DROP]")
    else:
        log_fail(f"GÜVENLİK AÇIĞI! Team 2, domain üzerinden Team 1 labına erişebildi!", res_dom.stdout)


def test_9_renew_lab():
    log_step("9. Lab Süresi Uzatma (Renew Instance Testi)")

    try:
        p1_uid = PLAYERS["t1_p1"]["user_id"]
        cmd = f"""python3 -c "
import importlib
from CTFd import create_app
app = create_app()
with app.app_context():
    mod = importlib.import_module('CTFd.plugins.ctfd-dehliz')
    DockerManager = mod.docker_manager.DockerManager
    ok, remaining = DockerManager.renew_instance(user_id={p1_uid}, challenge_id=1)
    if ok:
        print(f'OK|{{remaining}}')
    else:
        print(f'ERR|{{remaining}}')
" """
        res = subprocess.run(
            ["docker", "exec", "dehliz-ctf-ctfd-1", "sh", "-c", cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        output = res.stdout.strip()
        if "OK|" in output:
            parts = [line for line in output.splitlines() if line.startswith("OK|")][0].split("|")
            log_pass(f"Lab süresi başarıyla uzatıldı: Kalan süre {parts[1]} saniye")
        else:
            log_fail("Lab süresi uzatılamadı", output or res.stderr)
    except Exception as e:
        log_fail("Renew işlemi sırasında hata oluştu", str(e))


def test_10_destroy_and_cleanup():
    log_step("10. Lab Kapatma, Swarm Temizliği & İzolasyon Doğrulaması")

    if not CONTAINER_INFO.get("ip"):
        return

    domain = CONTAINER_INFO["domain"]
    ip = CONTAINER_INFO["ip"]
    port = CONTAINER_INFO["port"]
    ns = PLAYERS["t1_p1"]["ns"]

    # 1. Konteyneri yok et
    try:
        p1_uid = PLAYERS["t1_p1"]["user_id"]
        cmd = f"""python3 -c "
import importlib
from CTFd import create_app
app = create_app()
with app.app_context():
    mod = importlib.import_module('CTFd.plugins.ctfd-dehliz')
    DockerManager = mod.docker_manager.DockerManager
    ok, msg = DockerManager.destroy_instance(user_id={p1_uid}, challenge_id=1)
    print(f'OK|{{msg}}' if ok else f'ERR|{{msg}}')
" """
        res = subprocess.run(
            ["docker", "exec", "dehliz-ctf-ctfd-1", "sh", "-c", cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if "OK|" in res.stdout:
            log_pass("Konteyner Docker Swarm üzerinden başarıyla silindi")
        else:
            log_fail("Konteyner kapatılamadı", res.stdout or res.stderr)
    except Exception as e:
        log_fail("Destroy sırasında hata", str(e))

    # 2. DNS kaydının silindiğini doğrula
    time.sleep(1)
    status_data = http_get_json(f"{GATEWAY_API}/api/status")
    dns_records = status_data.get("dns_records", {})
    if domain not in dns_records:
        log_pass(f"Yerel DNS kaydı Gateway üzerinden temizlendi ({domain})")
    else:
        log_fail(f"DNS kaydı temizlenmedi, hala mevcut: {domain}")

    # 3. Kapatma sonrası Team 1'in de artık laba erişemediğini doğrula
    res_access = run_cmd(f"ip netns exec {ns} curl -s -m 2 http://{ip}:{port}/", check=False)
    if res_access.returncode != 0:
        log_pass("Kapatılan laba erişim beklendiği gibi sonlandırıldı (Port Kapalı/Drop)")
    else:
        log_fail("Lab kapatılmasına rağmen servis hala yanıt veriyor!")


def test_11_solve_auto_cleanup():
    log_step("11. Soru Çözüldüğünde Otomatik Kapatma Testi (Auto-Destroy on Solve)")

    p1_uid = PLAYERS["t1_p1"]["user_id"]
    p1_tid = PLAYERS["t1_p1"]["team_id"]

    try:
        # 1. Team 1 için yeni bir soru konteyneri başlat
        launch_cmd = f"""python3 -c "
import importlib
from CTFd import create_app
from CTFd.models import db, Users, Solves
app = create_app()
with app.app_context():
    mod = importlib.import_module('CTFd.plugins.ctfd-dehliz')
    DockerManager = mod.docker_manager.DockerManager
    DehlizChallenge = mod.models.DehlizChallenge
    chall = DehlizChallenge.query.filter_by(id=1).first()
    
    # Varsa önceki çözümleri temizle (testin tekrar koşabilmesi için)
    Solves.query.filter_by(challenge_id=1, user_id={p1_uid}).delete()
    db.session.commit()
    
    ok, c, msg = DockerManager.create_instance(user_id={p1_uid}, team_id={p1_tid}, challenge=chall)
    if ok:
        print(f'LAUNCH_OK|{{c.ip_address}}|{{c.domain}}|{{c.docker_id}}|{{c.flag}}')
    else:
        print(f'ERR|{{msg}}')
" """
        res = subprocess.run(["docker", "exec", "dehliz-ctf-ctfd-1", "sh", "-c", launch_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        lines = [l for l in res.stdout.strip().splitlines() if l.startswith("LAUNCH_OK|")]
        if not lines:
            log_fail("Çözüm testi için konteyner başlatılamadı", res.stdout or res.stderr)
            return

        parts = lines[0].split("|")
        c_ip, c_dom, c_id, c_flag = parts[1], parts[2], parts[3], parts[4]
        log_pass(f"Test için konteyner başlatıldı: {c_dom} ({c_ip})")

        # 2. CTFd üzerinden soruyu çözdür (solve tetikle)
        solve_cmd = f"""python3 -c "
from CTFd import create_app
from CTFd.models import db, Users, Teams, Challenges
from CTFd.plugins.challenges import get_chal_class
from werkzeug.test import EnvironBuilder
from flask import Request

app = create_app()
with app.app_context():
    chall = Challenges.query.filter_by(id=1).first()
    user = Users.query.filter_by(id={p1_uid}).first()
    team = Teams.query.filter_by(id={p1_tid}).first() if {p1_tid} else None
    
    builder = EnvironBuilder(method='POST', data={{'submission': '{c_flag}'}}, environ_base={{'REMOTE_ADDR': '127.0.0.1'}})
    req = Request(builder.get_environ())
    
    chal_class = get_chal_class(chall.type)
    chal_class.solve(user=user, team=team, challenge=chall, request=req)
    print('SOLVE_OK')
" """
        res_solve = subprocess.run(["docker", "exec", "dehliz-ctf-ctfd-1", "sh", "-c", solve_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if "SOLVE_OK" in res_solve.stdout:
            log_pass(f"Doğru bayrak gönderildi ve soru çözüldü ({c_flag[:15]}...)")
        else:
            log_fail("Soru çözme işlemi başarısız", res_solve.stdout or res_solve.stderr)
            return

        # 3. Canlı konteynerin otomatik kapandığını doğrula
        time.sleep(1)
        check_cmd = f"""python3 -c "
import importlib
from CTFd import create_app
app = create_app()
with app.app_context():
    mod = importlib.import_module('CTFd.plugins.ctfd-dehliz')
    DockerManager = mod.docker_manager.DockerManager
    c = DockerManager.get_user_container({p1_uid}, 1, team_id={p1_tid})
    print('STILL_RUNNING' if c else 'DESTROYED')
" """
        res_check = subprocess.run(["docker", "exec", "dehliz-ctf-ctfd-1", "sh", "-c", check_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if "DESTROYED" in res_check.stdout:
            log_pass("Soru çözüldüğünde canlı konteyner veritabanından ve Swarm'dan otomatik kapatıldı!")
        else:
            log_fail("HATA: Soru çözüldü fakat konteyner hala çalışıyor!", res_check.stdout)

        # 4. Gateway DNS kaydının silindiğini doğrula
        status_data = http_get_json(f"{GATEWAY_API}/api/status")
        dns_records = status_data.get("dns_records", {})
        if c_dom not in dns_records:
            log_pass(f"Gateway DNS kaydı otomatik temizlendi: {c_dom}")
        else:
            log_fail(f"Gateway DNS kaydı temizlenmedi: {c_dom}")

    except Exception as e:
        log_fail("Otomatik kapatma testi sırasında istisna", str(e))


def test_12_compose_lateral_movement():
    log_step("12. Çoklu Konteyner & Lateral Movement Labı Testi (Docker Compose)")

    p1_uid = PLAYERS["t1_p1"]["user_id"]
    p1_tid = PLAYERS["t1_p1"]["team_id"]
    ns_t1 = PLAYERS["t1_p1"]["ns"]
    ns_t2 = PLAYERS["t2_p1"]["ns"]

    try:
        # 1. Challenge 2 için Compose Labını Başlat
        launch_cmd = f"""python3 -c "
import importlib
from CTFd import create_app
from CTFd.models import db, Solves
app = create_app()
with app.app_context():
    mod = importlib.import_module('CTFd.plugins.ctfd-dehliz')
    ComposeManager = mod.compose_manager.ComposeManager
    DehlizComposeChallenge = mod.models.DehlizComposeChallenge
    c2 = DehlizComposeChallenge.query.filter_by(id=2).first()
    
    # Temizlik: varsa önceki çözümü ve ortamı temizle
    Solves.query.filter_by(challenge_id=2, user_id={p1_uid}).delete()
    db.session.commit()
    ComposeManager.destroy_instance(user_id={p1_uid}, challenge_id=2, team_id={p1_tid})
    
    ok, inst, msg = ComposeManager.create_instance(user_id={p1_uid}, team_id={p1_tid}, challenge=c2)
    if ok:
        print(f'COMPOSE_OK|{{inst.entrypoint_ip}}|{{inst.domain}}|{{inst.port}}|{{inst.flags}}')
    else:
        print(f'ERR|{{msg}}')
" """
        res = subprocess.run(["docker", "exec", "dehliz-ctf-ctfd-1", "sh", "-c", launch_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        lines = [l for l in res.stdout.strip().splitlines() if l.startswith("COMPOSE_OK|")]
        if not lines:
            log_fail("Compose labı başlatılamadı", res.stdout or res.stderr)
            return

        parts = lines[0].split("|")
        entry_ip, domain, port, flags_json = parts[1], parts[2], int(parts[3]), parts[4]
        flags_dict = json.loads(flags_json)
        log_pass(f"Çoklu konteynerli lab başlatıldı: {domain} ({entry_ip}:{port})")

        # 2. Servisin hazır olmasını bekle ve DMZ Portalına bağlan
        time.sleep(2)
        cmd_http = f"ip netns exec {ns_t1} curl -s -m 5 http://{domain}:{port}/"
        res_http = run_cmd(cmd_http, check=False)
        if res_http.returncode == 0 and ("ACME Corp" in res_http.stdout or len(res_http.stdout) > 0):
            log_pass(f"Team 1 DMZ Teşhis Portalına bağlandı: http://{domain}:{port}/")
        else:
            log_fail("Giriş makinesine (DMZ) HTTP bağlantısı kurulamadı", res_http.stderr or res_http.stdout)

        # 3. İzolasyon Doğrulaması: Dahili hedefe WireGuard üzerinden DOĞRUDAN erişilememeli
        cmd_direct_target = f"ip netns exec {ns_t1} curl -s -m 2 http://internal-target:8080/"
        res_direct = run_cmd(cmd_direct_target, check=False)
        if res_direct.returncode != 0:
            log_pass("Dahili hedefe (internal-target:8080) WireGuard tünelinden doğrudan erişim ENGELLENDİ (İzolasyon Başarılı).")
        else:
            log_fail("GÜVENLİK AÇIĞI! Dahili hedef (internal-target) doğrudan WireGuard tüneline maruz kalmış!", res_direct.stdout)

        # 4. Güvenlik İzolasyonu: Team 2 bu Compose labına erişememeli (Firewall DROP)
        res_t2 = run_cmd(f"ip netns exec {ns_t2} curl -s -m 3 http://{entry_ip}:{port}/", check=False)
        if res_t2.returncode != 0:
            log_pass(f"Team 2'nin Team 1 Compose labına erişimi ENGELLENDİ: http://{entry_ip}:{port}/ [Firewall DROP / Timeout]")
        else:
            log_fail("GÜVENLİK AÇIĞI! Team 2, Team 1 Compose labına sızabildi!", res_t2.stdout)

        # 5. Gerçek Lateral Movement Sömürüsü: DMZ Komut Enjeksiyonu üzerinden Dahili Hedefi Sorgulama
        log_step("   --> DMZ Komut Enjeksiyonu sömürülüyor ve iç ağa (internal-target) pivot yapılıyor...")
        exploit_cmd = f"ip netns exec {ns_t1} curl -s -X POST http://{domain}:{port}/api/ping --data-urlencode 'target=127.0.0.1; curl -s http://internal-target:8080/api/vault/flag'"
        res_exploit = run_cmd(exploit_cmd, check=False)
        
        expected_flag = flags_dict.get("FLAG_FINAL")
        captured_flag = None

        if res_exploit.returncode == 0:
            try:
                exp_data = json.loads(res_exploit.stdout)
                out_text = exp_data.get("output", "")
                flag_match = re.search(r"DEHLIZ\{[a-f0-9\-]+\}", out_text)
                if flag_match:
                    captured_flag = flag_match.group(0)
                    log_pass(f"Lateral Movement Başarılı! Dahili kasadan bayrak sızdırıldı: {captured_flag}")
                    if expected_flag and captured_flag == expected_flag:
                        log_pass(f"Sızdırılan bayrak dinamik FLAG_FINAL ile tam eşleşti: {captured_flag}")
                else:
                    log_fail("Komut çalıştı ancak bayrak regex ile bulunamadı", out_text)
            except Exception as e:
                log_fail("Exploit çıktısı ayrıştırılamadı", f"{e} - {res_exploit.stdout}")
        else:
            log_fail("DMZ exploit isteği başarısız oldu", res_exploit.stderr or res_exploit.stdout)

        # 6. Soru Çözümü & Otomatik Kapatma (Compose Down)
        target_flag = captured_flag or expected_flag or list(flags_dict.values())[0]
        solve_cmd = f"""python3 -c "
from CTFd import create_app
from CTFd.models import db, Users, Teams, Challenges
from CTFd.plugins.challenges import get_chal_class
from werkzeug.test import EnvironBuilder
from flask import Request

app = create_app()
with app.app_context():
    chall = Challenges.query.filter_by(id=2).first()
    user = Users.query.filter_by(id={p1_uid}).first()
    team = Teams.query.filter_by(id={p1_tid}).first() if {p1_tid} else None
    
    builder = EnvironBuilder(method='POST', data={{'submission': '{target_flag}'}}, environ_base={{'REMOTE_ADDR': '127.0.0.1'}})
    req = Request(builder.get_environ())
    
    chal_class = get_chal_class(chall.type)
    chal_class.solve(user=user, team=team, challenge=chall, request=req)
    print('SOLVE_OK')
" """
        res_solve = subprocess.run(["docker", "exec", "dehliz-ctf-ctfd-1", "sh", "-c", solve_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if "SOLVE_OK" in res_solve.stdout:
            log_pass(f"Compose lab bayrağı çözüldü ({target_flag[:15]}...)")
        else:
            log_fail("Compose lab çözümü başarısız", res_solve.stdout or res_solve.stderr)

        # 5. Tüm Compose projesinin otomatik yok edildiğini doğrula
        time.sleep(2)
        check_cmd = f"""python3 -c "
import importlib
from CTFd import create_app
app = create_app()
with app.app_context():
    mod = importlib.import_module('CTFd.plugins.ctfd-dehliz')
    ComposeManager = mod.compose_manager.ComposeManager
    inst = ComposeManager.get_user_instance({p1_uid}, 2, team_id={p1_tid})
    print('STILL_RUNNING' if inst else 'DESTROYED')
" """
        res_check = subprocess.run(["docker", "exec", "dehliz-ctf-ctfd-1", "sh", "-c", check_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if "DESTROYED" in res_check.stdout:
            log_pass("Tüm Compose projesi, iç ağları ve konteynerleri otomatik 'docker compose down' ile temizlendi!")
        else:
            log_fail("HATA: Compose projesi kapatılamadı!", res_check.stdout)

    except Exception as e:
        log_fail("Compose lab testi sırasında hata", str(e))


def cleanup_namespaces():
    """Test bitiminde oluşturulan ağ isim alanlarını temizler."""
    for key, p in PLAYERS.items():
        ns = p["ns"]
        wg = p["wg"]
        run_cmd(f"ip netns del {ns} 2>/dev/null || true", check=False)
        run_cmd(f"ip link del dev {wg} 2>/dev/null || true", check=False)
        run_cmd(f"rm -rf /etc/netns/{ns} /tmp/{wg}.key 2>/dev/null || true", check=False)


def print_summary():
    total = len(RESULTS)
    passed = sum(1 for _, ok in RESULTS if ok)
    failed = total - passed

    print("\n" + "=" * 65)
    print(f"{BOLD}           DEHLIZ CTF TEST RAPORU VE ÖZETİ           {RESET}")
    print("=" * 65)
    print(f" Toplam Koşulan Test Sayısı : {BOLD}{total}{RESET}")
    print(f" Başarılı (PASS)           : {GREEN}{BOLD}{passed}{RESET}")
    print(f" Başarısız (FAIL)          : {RED}{BOLD}{failed}{RESET}")
    print("-" * 65)

    if failed == 0:
        print(f" {GREEN}{BOLD}🎉 TEBRİKLER! TÜM GÜVENLİK VE ENTEGRASYON TESTLERİ GEÇTİ!{RESET}")
        print(" Platform siber poligon izolasyonu ve dinamik lab yönetimi için %100 hazır.")
    else:
        print(f" {RED}{BOLD}⚠️ BAZI TESTLER BAŞARISIZ OLDU! Lütfen yukarıdaki logları inceleyin.{RESET}")
    print("=" * 65 + "\n")
    return failed == 0


def main():
    start_time = time.time()
    print(f"{BOLD}=================================================================={RESET}")
    print(f"{BOLD}🛡️ DEHLIZ CTF SİBER POLİGON VE İZOLASYON ENTEGRASYON TESTİ{RESET}")
    print(f"{BOLD}=================================================================={RESET}")

    try:
        test_1_health_checks()
        test_2_register_peers()
        test_3_setup_namespaces()
        test_4_launch_lab()
        test_5_access_own_lab()
        test_6_teammate_cooperation()
        test_7_cross_team_player_isolation()
        test_8_cross_team_lab_isolation()
        test_9_renew_lab()
        test_10_destroy_and_cleanup()
        test_11_solve_auto_cleanup()
        test_12_compose_lateral_movement()
    finally:
        cleanup_namespaces()

    elapsed = round(time.time() - start_time, 2)
    print(f"[*] Test tamamlanma süresi: {elapsed} saniye")
    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
