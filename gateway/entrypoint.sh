#!/bin/bash
set -euo pipefail

WG_DIR="/etc/wireguard"
mkdir -p "$WG_DIR"

WG_HOST="${WG_HOST:-127.0.0.1}"
WG_PORT="${WG_PORT:-51820}"
DEHLIZ_DOMAIN="${DEHLIZ_DOMAIN:-dehliz.local}"

echo "=================================================="
echo "🛡️ Dehliz CTF WireGuard Gateway Başlatılıyor..."
echo "=================================================="

# 1. Server anahtar çifti kontrolü (Kalıcı depolama)
if [ ! -f "$WG_DIR/server.key" ]; then
    echo "[*] Yeni sunucu WireGuard anahtar çifti üretiliyor..."
    wg genkey | tee "$WG_DIR/server.key" | wg pubkey > "$WG_DIR/server.pub"
fi

SERVER_PRIV=$(cat "$WG_DIR/server.key")

# 2. Temel sunucu wg0.conf dosyasını oluştur (Eğer yoksa)
if [ ! -f "$WG_DIR/wg0.conf" ]; then
    cat <<EOF > "$WG_DIR/wg0.conf"
[Interface]
Address = 10.13.37.1/16
ListenPort = 51820
PrivateKey = $SERVER_PRIV
EOF
fi

# 3. İleri yönlendirme, Firewall ve DNS hazırlığı
echo "[*] Ağ yönlendirme ve iptables kuralları hazırlanıyor..."
iptables -F FORWARD
iptables -t nat -F POSTROUTING
iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -t nat -A POSTROUTING -o eth+ -j MASQUERADE

# Tünel içinden Gateway DNS sorgularına izin ver (Port 53)
iptables -I INPUT 1 -i wg0 -p udp --dport 53 -j ACCEPT
iptables -I INPUT 2 -i wg0 -p tcp --dport 53 -j ACCEPT

# 4. Yerel DNS Sunucusu (dnsmasq) Hazırlığı
touch "$WG_DIR/hosts"
cat <<EOF > /etc/dnsmasq.conf
listen-address=10.13.37.1,127.0.0.1
bind-interfaces
no-resolv
server=1.1.1.1
server=8.8.8.8
domain=$DEHLIZ_DOMAIN
local=/$DEHLIZ_DOMAIN/
addn-hosts=$WG_DIR/hosts
EOF

# 5. WireGuard Arayüzünü Başlat
echo "[*] wg0 arayüzü başlatılıyor..."
wg-quick up wg0
ip route replace 10.13.0.0/16 dev wg0

# 6. dnsmasq DNS Sunucusunu Başlat
echo "[*] dnsmasq DNS sunucusu başlatılıyor (10.13.37.1:53)..."
dnsmasq -C /etc/dnsmasq.conf

# 7. Dinamik VPN Yönetim API'sini Başlat
echo "[*] WireGuard Dinamik Yönetim API'si başlatılıyor (Port: 5000)..."
python3 /usr/local/bin/vpn_manager.py &

echo "=================================================="
echo "✅ Dehliz CTF WireGuard Gateway, DNS & API Hazır!"
echo "   WireGuard Tünel : $WG_PORT/UDP"
echo "   Yerel DNS       : 10.13.37.1:53 ($DEHLIZ_DOMAIN)"
echo "   Yönetim API     : 5000/TCP (dehliz_internal)"
echo "=================================================="

trap "echo 'Durduruluyor...'; wg-quick down wg0; exit 0" SIGTERM SIGINT
sleep infinity &
wait $!
