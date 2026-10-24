#!/bin/bash
# Dehliz CTF Otomatik Siber Poligon Test Koşucusu (Bash)
# ============================================================

set -euo pipefail

echo "=================================================="
echo "🛡️ Dehliz CTF Siber Poligon Testi Başlatılıyor..."
echo "=================================================="

# 1. Test runner imajını derle
echo "[*] Test imajı kontrol ediliyor..."
docker build -t dehliz-test-runner -f tests/Dockerfile .

# 2. Test konteynerini çalıştır
echo "[*] Test paketi ağ tünelleri ve isim alanları içinde koşturuluyor..."
docker run --rm \
  --name dehliz-cyber-range-tester \
  --network dehliz-ctf_dehliz_bridge \
  --cap-add=NET_ADMIN \
  --cap-add=SYS_ADMIN \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/tests:/app/tests" \
  dehliz-test-runner
