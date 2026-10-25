# 🛡️ Dehliz CTF — Yeni Nesil Siber Tatbikat Sahası (Cyber Range)

[![WireGuard](https://img.shields.io/badge/VPN-WireGuard-88171a.svg?style=flat-square&logo=wireguard)](https://www.wireguard.com/)
[![CTFd](https://img.shields.io/badge/Platform-CTFd%20v3.6-blue.svg?style=flat-square)](https://ctfd.io/)
[![Docker Swarm](https://img.shields.io/badge/Orchestration-Docker%20Swarm-2496ED.svg?style=flat-square&logo=docker)](https://docs.docker.com/engine/swarm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

> _"Karanlıkta kalan portlar, aşılamaz surlar ve sadece tünelden sızılabilen bir siber poligon."_

**Dehliz CTF**, CTFd platformunu tek bir komutla Hack The Box / Cyber Range kalitesinde **izole, multi-tenant ve şifreli tünelli bir siber tatbikat sahasına** dönüştüren açık kaynaklı bir altyapı motorudur.

Geleneksel CTF'lerin FRP port karmaşasını (`185.x.x.x:31452`) tarihe gömer; sıfır dış port kuralı, takım içi serbest haberleşme, tam takım izolasyonu ve otomatik yerel DNS (`*.dehliz.local`) sunar.

---

## 🌟 Neden Dehliz CTF? (Geleneksel FRP vs Dehliz)

| Özellik                           | Geleneksel CTFd + FRP                        | 🛡️ Dehliz CTF                                                |
| :-------------------------------- | :------------------------------------------- | :----------------------------------------------------------- |
| **Dış Port Güvenliği**            | Her soru için internete rastgele port açılır | **0 Dış Port!** Konteynerler internete tamamen kapalıdır     |
| **Bağlantı Türü**                 | TCP Port Forwarding                          | **WireGuard Kriptografik Şifreli Tünel**                     |
| **Ad Çözümleme (DNS)**            | Yok (Yalnızca çirkin IP ve portlar)          | **Otomatik Yerel DNS:** `http://soru-adi.dehliz.local`       |
| **Ters Bağlantı (Reverse Shell)** | İmkansız / Çok Zor (Modem NAT engeli)        | **Doğrudan Oyuncunun VPN IP'sine:** `nc 10.13.1.2 4444`      |
| **Ağ Taraması (Port Scan)**       | Yapılamaz (Yalnızca verilen tek port)        | **Tam Nmap Desteği:** `nmap soru-adi.dehliz.local`           |
| **Takım İzolasyonu**              | Yok (Takımlar birbirine saldırabilir)        | **Çekirdek Düzeyinde `iptables` Mikro-Bölümleme (DROP)**     |
| **Takım İçi İşbirliği**           | Yok                                          | **Serbest:** Takım arkadaşları birbirinin IP'sine erişebilir |
| **Kaynak Tüketimi**               | Ağır Java/Go proxy'leri                      | **Ultra Hafif:** Alpine Linux Gateway (~50 MB RAM!)          |

---

## 🏛️ Mimari Şema & Ağ Topolojisi

```mermaid
flowchart TD
    subgraph Clients["1. YARIŞMACILAR & TAKIMLAR"]
        subgraph Team1["Takım 1 (10.13.1.0/24)"]
            T1_P1["Oyuncu 1<br/>10.13.1.1"]
            T1_P2["Oyuncu 2<br/>10.13.1.2"]
            T1_P1 <-->|"Takım İçi İşbirliği"| T1_P2
        end
        subgraph Team2["Takım 2 (10.13.2.0/24)"]
            T2_P1["Oyuncu 1<br/>10.13.2.1"]
            T2_P2["Oyuncu 2<br/>10.13.2.2"]
        end
    end

    subgraph Gateway["2. DEHLIZ GATEWAY (10.13.37.1)"]
        WGIface["WireGuard wg0 (51820/UDP)"]
        DNS["dnsmasq (Port 53) • *.dehliz.local"]
        IPTables["Dinamik iptables Mikro-Bölümleme"]
        API["Yönetim API'si (Port 5000)"]
    end

    subgraph Overlay["3. İZOLE DOCKER SWARM SORU HAVUZU (dehliz_containers: 10.0.1.0/24)"]
        Chall1["kampus-bulteni.dehliz.local<br/>10.0.1.122:5000"]
        Chall2["akilli-kartim.dehliz.local<br/>10.0.1.100:80"]
        Chall3["gece-kantini.dehliz.local<br/>10.0.1.42:5000"]
    end

    Team1 ==>|"WireGuard Tüneli"| WGIface
    Team2 ==>|"WireGuard Tüneli"| WGIface
    Team1 x-.-x|"İzole / Engellendi"| Team2

    WGIface --> DNS
    WGIface --> IPTables
    IPTables ==>|"Yönlendirme"| Chall1
    IPTables ==>|"Yönlendirme"| Chall2
    IPTables ==>|"Yönlendirme"| Chall3

    Chall1 -.->|"Ters Bağlantı (nc 10.13.1.2 4444)"| T1_P2
```

---

## ⚡ Hızlı Kurulum (Quickstart)

### Gereksinimler:

- Linux (Ubuntu / Debian / CentOS / Arch) veya Windows (Docker Desktop WSL2)
- Docker & Docker Compose v2+

### 1. Depoyu Klonlayın

```bash
git clone https://github.com/your-username/dehliz-ctf.git
cd dehliz-ctf
```

### 2. Tek Komutla Kurulumu Başlatın

**Linux / macOS:**

```bash
chmod +x install.sh
./install.sh
```

**Windows (PowerShell):**

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\install.ps1
```

Kurulum tamamlandığında:

- **CTFd Web Paneli:** `http://localhost:8000`
- **WireGuard Portu:** `51820/UDP`
- **Yerel DNS:** `10.13.37.1:53` (\*.dehliz.local)

---

## ⚙️ Yapılandırma (`.env`)

Sistem ayarlarını özelleştirmek için `.env` dosyasını düzenleyebilirsiniz:

```ini
# Sunucunuzun yarışmacılara açık olan Dış IP adresi veya Domain'i
WG_HOST=192.168.1.100
WG_PORT=51820

# Soru makinelerine atanacak özel alan adı uzantısı
DEHLIZ_DOMAIN=dehliz.local

# CTFd Güvenlik Anahtarı
SECRET_KEY=super_gizli_uretim_anahtari_2026
```

---

## 🚀 Soru Ekleme & Geliştirme

Dehliz CTF için soru hazırlamak çok kolaydır:

1. `examples/sample-challenge` dizinindeki hazır şablonu inceleyin.
2. Konteynerinizi oluşturup build edin:
   ```bash
   docker build -t mychall:latest examples/sample-challenge
   ```
3. CTFd Admin panelinde **Whale** eklentisinden yeni soru oluşturup imaj adı olarak `mychall:latest` belirtin.
4. Soru başladığında yarışmacıya otomatik olarak `http://mychall.dehliz.local` linki atanacaktır!

---

## 🧪 Otomatik Siber Poligon & Güvenlik İzolasyon Testleri

Dehliz CTF, tüm mikro-bölümleme kurallarını, WireGuard tünellerini, Swarm yaşam döngüsünü ve takımlar arası izolasyonu uçtan uca doğrulayan otomatik bir test paketine sahiptir.

### Tek Komutla Testleri Çalıştırma:

**Windows (PowerShell):**
```powershell
.\tests\run_tests.ps1
```

**Linux / macOS (Bash):**
```bash
chmod +x ./tests/run_tests.sh
./tests/run_tests.sh
```

### Otomatik Olarak Doğrulanan Senaryolar:
1. **Altyapı Kontrolü:** WireGuard Gateway API, CTFd ve Docker Swarm Overlay ağı.
2. **Dinamik Peer & Tünel:** Takım 1 (2 oyuncu) ve Takım 2 (1 oyuncu) için anahtar üretimi ve canlı tünel el sıkışması (`10.13.37.1`).
3. **Lab Yaşam Döngüsü:** Dinamik soru başlatma, Swarm IP tespiti ve Gateway yerel DNS (`*.dehliz.local`) kaydı.
4. **Yetkili Erişim:** Takım oyuncusunun yerel DNS ve direkt IP üzerinden kendi labına erişimi (`HTTP 200 OK`).
5. **Takım İçi İşbirliği:** Aynı takımdaki oyuncuların birbirinin VPN IP'sine serbestçe erişebilmesi (`ping 0% kayıp`).
6. **Takımlar Arası Oyuncu İzolasyonu:** Rakip takımın diğer takımın oyuncularına saldırmasının engellenmesi (`Firewall DROP`).
7. **Takımlar Arası Lab İzolasyonu:** Rakip takımın diğer takımın soru labına sızmasının engellenmesi (`Firewall DROP / Timeout`).
8. **Süre Uzatma & Temizlik:** Lab yenileme, kapatma, Swarm konteynerinin silinmesi ve DNS/Firewall kurallarının temizlenmesi.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır. Eğitim, akademik ve ticari amaçlarla özgürce kullanılabilir ve geliştirilebilir.
