import os
import re
import time
import requests
from ...models import WhaleContainer
from .base import BaseRouter
from CTFd.models import db

VPN_API_URL = os.environ.get("VPN_API_URL", "http://vpn-gateway:5000")


class WireguardRouter(BaseRouter):
    name = "wireguard"

    def __init__(self):
        super().__init__()

    def register(self, container: WhaleContainer):
        """FRP port havuzuna gerek duymadan doğrudan konteynerin iç portunu kaydeder."""
        container.port = container.challenge.redirect_port or 8080
        db.session.commit()
        return True, "success"

    def unregister(self, container: WhaleContainer):
        return True, "success"

    def get_challenge_domain(self, container: WhaleContainer):
        """Soru adından yerel domain üretir (Varsayılan: *.dehliz.local)."""
        raw_name = getattr(container.challenge, "name", "chall") or "chall"
        # Türkçe karakterleri ve özel karakterleri slugify et
        tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
        clean_name = raw_name.translate(tr_map)
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", clean_name).strip("-").lower()
        domain_suffix = os.environ.get("DEHLIZ_DOMAIN", "dehliz.local")
        return f"{slug}.{domain_suffix}"

    def register_dns(self, domain, ip):
        """Gateway içindeki dnsmasq servisine canlı yerel DNS kaydı ekler."""
        try:
            requests.post(
                f"{VPN_API_URL}/api/dns",
                json={"domain": domain, "ip": ip},
                timeout=2
            )
        except Exception:
            pass

    def access(self, container: WhaleContainer):
        """Yarışmacıya yerel domain ve tünel IP adresini gösterir."""
        ip = self.get_container_ip(container)
        port = container.challenge.redirect_port or container.port or 8080
        cat = str(getattr(container.challenge, "category", "") or "").lower()
        domain = self.get_challenge_domain(container)

        # Eğer gerçek bir IP adresi çözümlendiyse DNS kaydını Gateway'e ekle
        is_real_ip = "." in ip and not ip.endswith(container.uuid)
        if is_real_ip:
            self.register_dns(domain, ip)

        target_host = domain if is_real_ip else ip

        if "web" in cat or port in (80, 443, 3000, 5000, 8000, 8080):
            return (
                '<div class="mb-2">'
                '<span class="badge badge-success px-2 py-1">🛡️ VPN &amp; Yerel DNS</span> '
                f'<small class="text-muted font-weight-bold">({ip})</small>'
                '</div>'
                f'<a target="_blank" class="btn btn-primary btn-sm text-white font-weight-bold shadow-sm" '
                f'href="http://{target_host}:{port}/">🌐 http://{target_host}:{port}</a>'
            )
        return (
            '<div class="mb-2">'
            '<span class="badge badge-success px-2 py-1">🛡️ VPN &amp; Yerel DNS</span> '
            f'<small class="text-muted font-weight-bold">({ip})</small>'
            '</div>'
            f'<code class="p-2 border rounded bg-light font-weight-bold text-dark">nc {target_host} {port}</code>'
        )

    def get_container_ip(self, container: WhaleContainer):
        """Docker Swarm overlay ağındaki dinamik konteyner IP'sini bulur."""
        try:
            from ..docker import DockerUtils
            service_name = f"{container.user_id}-{container.uuid}"
            service = DockerUtils.client.services.get(service_name)
            
            # Görevin ağ adresini çek (1-2 sn içinde atanır)
            for _ in range(5):
                tasks = service.tasks()
                for t in tasks:
                    for att in t.get("NetworksAttachments", []):
                        addrs = att.get("Addresses", [])
                        if addrs:
                            return addrs[0].split("/")[0]
                time.sleep(0.3)
        except Exception:
            pass

        # Atanma gecikirse Swarm DNS alias'ını döndür
        return f"{container.user_id}-{container.uuid}"

    def check_availability(self):
        return True, "Available"
