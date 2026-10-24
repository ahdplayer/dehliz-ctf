#!/usr/bin/env bash
set -euo pipefail

# ==========================================================
# 🛡️ Dehliz CTF - Linux / macOS Kurulum Betiği
# ==========================================================

echo -e "\033[0;36m==========================================================\033[0m"
echo -e "\033[0;36m🛡️  Dehliz CTF - Yeni Nesil Siber Poligon Kurulum Sihirbazı\033[0m"
echo -e "\033[0;36m==========================================================\033[0m"

# 1. Docker Kontrolü
if ! command -v docker &> /dev/null; then
    echo -e "\033[0;31m[!] Hata: Docker bulunamadı. Lütfen Docker'ı kurup başlatın.\033[0m"
    exit 1
fi

# 2. Docker Swarm Kontrolü
swarm_state=$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null || true)
if [ "$swarm_state" != "active" ]; then
    echo -e "\033[0;33m[*] Docker Swarm aktif değil. Swarm modu başlatılıyor...\033[0m"
    docker swarm init
else
    echo -e "\033[0;32m[+] Docker Swarm zaten aktif.\033[0m"
fi

# 3. Overlay Ağı Kontrolü
if ! docker network ls --filter name=^dehliz_containers$ -q | grep -q .; then
    echo -e "\033[0;33m[*] dehliz_containers izole overlay ağı oluşturuluyor...\033[0m"
    docker network create -d overlay --attachable dehliz_containers
else
    echo -e "\033[0;32m[+] dehliz_containers ağı mevcut.\033[0m"
fi

# 4. .env Dosyası
if [ ! -f .env ]; then
    echo -e "\033[0;33m[*] .env dosyası oluşturuluyor...\033[0m"
    cp .env.example .env
fi

# 5. Dizinler
dirs=(".data/wireguard" ".data/mysql" ".data/redis" ".data/CTFd/logs" ".data/CTFd/uploads")
for d in "${dirs[@]}"; do
    mkdir -p "$d"
done

# 6. Başlatma
echo -e "\033[0;36m[*] Dehliz CTF konteynerleri derleniyor ve başlatılıyor...\033[0m"
docker compose up -d --build

echo -e "\n\033[0;32m==========================================================\033[0m"
echo -e "\033[0;32m🎉 Dehliz CTF Başarıyla Kuruldu ve Çalışıyor!\033[0m"
echo -e "\033[0;32m==========================================================\033[0m"
echo -e "🌐 CTFd Yönetim Paneli : http://localhost:8000"
echo -e "🛡️ WireGuard Gateway   : 51820/UDP"
echo -e "📡 Yerel DNS Alan Adı  : *.dehliz.local"
echo -e "\033[0;32m==========================================================\033[0m"
