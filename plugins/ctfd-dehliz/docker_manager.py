import os
import re
import time
import uuid
import datetime
import docker
import requests
from flask import current_app
from CTFd.models import db
from CTFd.utils import get_config
from .models import DehlizContainer, DehlizChallenge

VPN_API_URL = os.environ.get("VPN_API_URL", "http://vpn-gateway:5000")
DEHLIZ_DOMAIN = os.environ.get("DEHLIZ_DOMAIN", "dehliz.local")
SWARM_NETWORK = "dehliz_containers"


def get_docker_client():
    return docker.from_env()


def parse_memory(mem_str):
    """Bellek katarını (128m, 1g vb.) bayta çevirir."""
    if not mem_str:
        return 128 * 1024 * 1024
    mem_str = str(mem_str).strip().lower()
    units = {"k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024}
    for unit, mult in units.items():
        if mem_str.endswith(unit):
            try:
                return int(float(mem_str[:-1]) * mult)
            except ValueError:
                return 128 * 1024 * 1024
    try:
        return int(mem_str)
    except ValueError:
        return 128 * 1024 * 1024


def slugify(text):
    """Türkçe karakterleri ve boşlukları URL/DNS dostu hale getirir."""
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    clean = text.translate(tr_map)
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", clean).strip("-").lower()
    return clean or "chall"


class DockerManager:
    @staticmethod
    def get_user_container(user_id, challenge_id):
        return DehlizContainer.query.filter_by(
            user_id=user_id,
            challenge_id=challenge_id
        ).first()

    @staticmethod
    def create_instance(user_id, team_id, challenge: DehlizChallenge):
        # 1. Kullanıcının/Takımın mevcut canlı konteyneri var mı?
        existing = DockerManager.get_user_container(user_id, challenge.id)
        if existing:
            if existing.expire_time > datetime.datetime.utcnow():
                return True, existing, "Konteyner zaten calisiyor."
            else:
                DockerManager.destroy_instance(user_id, challenge.id)

        # 2. Maksimum global konteyner sınır kontrolü
        max_limit = int(get_config("dehliz:max_containers", 100))
        active_count = DehlizContainer.query.count()
        if active_count >= max_limit:
            return False, None, "Sunucu uzerindeki maksimum soru sinirina ulasildi. Lutfen biraz bekleyin."

        client = get_docker_client()

        # 3. Dinamik Bayrak ve Servis Adı
        flag = f"DEHLIZ{{{uuid.uuid4()}}}"
        identifier = f"t{team_id}" if team_id else f"u{user_id}"
        service_name = f"dehliz-{identifier}-c{challenge.id}"

        # 4. Daha önceden asılı kalmış aynı isimli servis varsa temizle
        try:
            old_service = client.services.get(service_name)
            old_service.remove()
            time.sleep(1)
        except Exception:
            pass

        # 5. Swarm Servisini Başlat
        mem_bytes = parse_memory(challenge.memory_limit)
        cpu_nanos = int(float(challenge.cpu_limit or 0.5) * 1e9)
        port = int(challenge.container_port or 80)

        try:
            service = client.services.create(
                image=challenge.docker_image,
                name=service_name,
                env={"FLAG": flag},
                networks=[SWARM_NETWORK],
                resources=docker.types.Resources(
                    mem_limit=mem_bytes,
                    cpu_limit=cpu_nanos
                ),
                restart_policy=docker.types.RestartPolicy(condition="none")
            )
        except Exception as e:
            return False, None, f"Docker servisi baslatilamadi: {str(e)}"

        # 6. Swarm Overlay Ağındaki Konteyner IP'sini Tespit Et
        container_ip = None
        for _ in range(20):
            try:
                tasks = service.tasks()
                for t in tasks:
                    for net in t.get("NetworksAttachments", []):
                        net_name = net.get("Network", {}).get("Spec", {}).get("Name")
                        if net_name == SWARM_NETWORK:
                            addrs = net.get("Addresses", [])
                            if addrs:
                                container_ip = addrs[0].split("/")[0]
                                break
                    if container_ip:
                        break
            except Exception:
                pass
            if container_ip:
                break
            time.sleep(0.5)

        if not container_ip:
            container_ip = service_name

        # 7. Çarpışmasız Dinamik Yerel Alan Adı Üret (Örn: kampus-bulteni-t1.dehliz.local)
        slug = slugify(challenge.name)
        domain = f"{slug}-{identifier}.{DEHLIZ_DOMAIN}"

        # 8. Gateway DNS Sunucusuna Canlı Kayıt Ekle
        try:
            requests.post(
                f"{VPN_API_URL}/api/dns",
                json={"domain": domain, "ip": container_ip},
                timeout=2
            )
        except Exception as e:
            current_app.logger.warning(f"[Dehliz CTF] DNS kayit uyarisi: {e}")

        # 9. Veritabanına Kaydet
        timeout_seconds = int(get_config("dehliz:timeout", 3600))
        expire_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=timeout_seconds)

        container_record = DehlizContainer(
            user_id=user_id,
            team_id=team_id,
            challenge_id=challenge.id,
            docker_id=service_name,
            ip_address=container_ip,
            domain=domain,
            port=port,
            flag=flag,
            start_time=datetime.datetime.utcnow(),
            expire_time=expire_time,
            renew_count=0
        )
        db.session.add(container_record)
        db.session.commit()

        return True, container_record, "Konteyner basariyla baslatildi."

    @staticmethod
    def destroy_instance(user_id, challenge_id=None, container_id=None):
        query = DehlizContainer.query
        if container_id:
            record = query.filter_by(id=container_id).first()
        else:
            record = query.filter_by(user_id=user_id, challenge_id=challenge_id).first()

        if not record:
            return False, "Calisan bir konteyner bulunamadi."

        client = get_docker_client()
        try:
            service = client.services.get(record.docker_id)
            service.remove()
        except Exception:
            pass

        db.session.delete(record)
        db.session.commit()
        return True, "Konteyner basariyla kapatildi."

    @staticmethod
    def renew_instance(user_id, challenge_id):
        record = DockerManager.get_user_container(user_id, challenge_id)
        if not record:
            return False, "Yenilenecek aktif bir konteyner bulunamadi."

        max_renews = int(get_config("dehliz:max_renews", 5))
        if record.renew_count >= max_renews:
            return False, f"Maksimum sure uzatma limitine ({max_renews}) ulastiniz."

        renew_seconds = int(get_config("dehliz:renew_time", 1800))
        record.expire_time = record.expire_time + datetime.timedelta(seconds=renew_seconds)
        record.renew_count += 1
        db.session.commit()

        remaining = int((record.expire_time - datetime.datetime.utcnow()).total_seconds())
        return True, remaining

    @staticmethod
    def cleanup_expired_instances():
        """Süresi dolmuş konteynerleri periyodik olarak temizler."""
        now = datetime.datetime.utcnow()
        expired = DehlizContainer.query.filter(DehlizContainer.expire_time <= now).all()
        client = get_docker_client()

        for c in expired:
            try:
                service = client.services.get(c.docker_id)
                service.remove()
            except Exception:
                pass
            db.session.delete(c)

        if expired:
            db.session.commit()
            print(f"[Dehliz CTF] {len(expired)} adet suresi dolmus konteyner temizlendi.")
