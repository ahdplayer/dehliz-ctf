# ==========================================================
# Dehliz CTF - Windows Kurulum Betigi (PowerShell)
# ==========================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Dehliz CTF - Yeni Nesil Siber Poligon Kurulum Sihirbazi" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Docker Kontrolu
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Hata: Docker bulunamadi. Lutfen Docker Desktop uygulamasini kurup baslatin." -ForegroundColor Red
    exit 1
}

# 2. Docker Swarm Kontrolu
$swarmState = (docker info --format '{{.Swarm.LocalNodeState}}')
if ($swarmState -ne "active") {
    Write-Host "[*] Docker Swarm aktif degil. Swarm modu baslatiliyor..." -ForegroundColor Yellow
    docker swarm init
} else {
    Write-Host "[+] Docker Swarm zaten aktif." -ForegroundColor Green
}

# 3. Overlay Agi Kontrolu
$netExists = docker network ls --filter name=^dehliz_containers$ -q
if (-not $netExists) {
    Write-Host "[*] dehliz_containers izole overlay agi olusturuluyor..." -ForegroundColor Yellow
    docker network create -d overlay --attachable dehliz_containers
} else {
    Write-Host "[+] dehliz_containers agi mevcut." -ForegroundColor Green
}

# 4. .env Dosyasi
if (-not (Test-Path .env)) {
    Write-Host "[*] .env dosyasi olusturuluyor..." -ForegroundColor Yellow
    Copy-Item .env.example .env
}

# 5. Dizinler
$dirs = @(".data/wireguard", ".data/mysql", ".data/redis", ".data/CTFd/logs", ".data/CTFd/uploads")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d -Force | Out-Null
    }
}

# 6. Baslatma
Write-Host "[*] Dehliz CTF konteynerleri derleniyor ve baslatiliyor..." -ForegroundColor Cyan
docker compose up -d --build

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[!] Hata: Docker Compose islemi sirasinda bir hata meydana geldi." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "[+] Dehliz CTF Basariyla Kuruldu ve Calisiyor!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "CTFd Yonetim Paneli : http://localhost:8000" -ForegroundColor White
Write-Host "WireGuard Gateway   : 51820/UDP" -ForegroundColor White
Write-Host "Yerel DNS Alan Adi  : *.dehliz.local" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Green
