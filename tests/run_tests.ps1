# Dehliz CTF Otomatik Siber Poligon Test Koşucusu (PowerShell)
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "🛡️ Dehliz CTF Siber Poligon Testi Başlatılıyor..." -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Test runner imajı hazır değilse derle
Write-Host "[*] Test imajı kontrol ediliyor..." -ForegroundColor Yellow
docker build -t dehliz-test-runner -f tests/Dockerfile .

# 2. Test konteynerini çalıştır
Write-Host "[*] Test paketi ağ tünelleri ve isim alanları içinde koşturuluyor..." -ForegroundColor Yellow
docker run --rm `
  --name dehliz-cyber-range-tester `
  --network dehliz-ctf_dehliz_bridge `
  --cap-add=NET_ADMIN `
  --cap-add=SYS_ADMIN `
  -v /var/run/docker.sock:/var/run/docker.sock `
  -v "${PWD}/tests:/app/tests" `
  dehliz-test-runner
