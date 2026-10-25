import os
import re
import time
import uuid
import json
import shutil
import datetime
import subprocess
import yaml
import requests
from flask import current_app
from CTFd.models import db
from CTFd.utils import get_config
from .models import DehlizComposeChallenge, DehlizComposeInstance
from .docker_manager import slugify, parse_memory

VPN_API_URL = os.environ.get("VPN_API_URL", "http://vpn-gateway:5000")
DEHLIZ_DOMAIN = os.environ.get("DEHLIZ_DOMAIN", "dehliz.local")
SWARM_NETWORK = "dehliz_containers"
COMPOSE_WORK_DIR = "/tmp/dehliz_compose"


class ComposeManager:
    @staticmethod
    def get_user_instance(user_id, challenge_id, team_id=None):
        if team_id:
            inst = DehlizComposeInstance.query.filter_by(
                team_id=team_id,
                challenge_id=challenge_id
            ).first()
            if inst:
                return inst
        return DehlizComposeInstance.query.filter_by(
            user_id=user_id,
            challenge_id=challenge_id
        ).first()

    @staticmethod
    def create_instance(user_id, team_id, challenge: DehlizComposeChallenge):
        # 1. Kullanıcının/Takımın mevcut canlı ortamı var mı?
        existing = ComposeManager.get_user_instance(user_id, challenge.id, team_id=team_id)
        if existing:
            if existing.expire_time > datetime.datetime.utcnow():
                return True, existing, "Compose ortami zaten calisiyor."
            else:
                ComposeManager.destroy_instance(user_id, challenge.id, team_id=team_id)

        # 2. Maksimum global compose sınır kontrolü
        max_limit = int(get_config("dehliz:max_compose_instances", 30))
        active_count = DehlizComposeInstance.query.count()
        if active_count >= max_limit:
            return False, None, "Sunucu uzerindeki maksimum compose lab sinirina ulasildi. Lutfen biraz bekleyin."

        # 3. Proje Adı Belirle
        identifier = f"t{team_id}" if team_id else f"u{user_id}"
        project_name = f"dehliz-c{challenge.id}-{identifier}".lower()

        # 4. Compose YAML İçeriğini Ayrıştır ve Giriş Noktasını Belirle
        raw_content = challenge.compose_content or ""
        try:
            compose_data = yaml.safe_load(raw_content) or {}
        except Exception as e:
            return False, None, f"Gecersiz docker-compose.yml formati: {str(e)}"

        services = compose_data.get("services", {})
        if not services:
            return False, None, "docker-compose.yml icerisinde tanimli hicbir servis bulunamadi."

        # Giriş servisini (Entrypoint) tespit et
        entrypoint_svc = None
        if challenge.entrypoint_service and challenge.entrypoint_service in services:
            entrypoint_svc = challenge.entrypoint_service
        else:
            for s_name, s_cfg in services.items():
                labels = s_cfg.get("labels", [])
                if isinstance(labels, list) and any("dehliz.entrypoint=true" in str(l).lower() for l in labels):
                    entrypoint_svc = s_name
                    break
                elif isinstance(labels, dict) and str(labels.get("dehliz.entrypoint", "")).lower() == "true":
                    entrypoint_svc = s_name
                    break

        if not entrypoint_svc:
            # Belirtilmemişse ilk servisi giriş noktası yap
            entrypoint_svc = list(services.keys())[0]

        # 5. Giriş Servisini 'dehliz_containers' Ağına Bağla
        if "networks" not in compose_data or not isinstance(compose_data["networks"], dict):
            compose_data["networks"] = {}

        compose_data["networks"][SWARM_NETWORK] = {"external": True}

        svc_cfg = services[entrypoint_svc]
        svc_nets = svc_cfg.get("networks", [])
        if isinstance(svc_nets, list):
            if SWARM_NETWORK not in svc_nets:
                svc_nets.append(SWARM_NETWORK)
            svc_cfg["networks"] = svc_nets
        elif isinstance(svc_nets, dict):
            svc_nets[SWARM_NETWORK] = {}
            svc_cfg["networks"] = svc_nets

        # 6. Dinamik Bayrakları Enjekte Et
        flags_dict = {}
        for s_name, s_cfg in services.items():
            env = s_cfg.get("environment", {})
            if isinstance(env, dict):
                for k, v in list(env.items()):
                    if "FLAG" in k.upper():
                        dyn_flag = f"DEHLIZ{{{uuid.uuid4()}}}"
                        env[k] = dyn_flag
                        flags_dict[k] = dyn_flag
                s_cfg["environment"] = env
            elif isinstance(env, list):
                new_env = []
                for item in env:
                    if "=" in item and "FLAG" in item.split("=")[0].upper():
                        k = item.split("=")[0]
                        dyn_flag = f"DEHLIZ{{{uuid.uuid4()}}}"
                        new_env.append(f"{k}={dyn_flag}")
                        flags_dict[k] = dyn_flag
                    else:
                        new_env.append(item)
                s_cfg["environment"] = new_env

        # Eğer hiçbir FLAG değişkeni yoksa ana bayrak üret
        if not flags_dict:
            main_flag = f"DEHLIZ{{{uuid.uuid4()}}}"
            flags_dict["FLAG"] = main_flag
            if isinstance(services[entrypoint_svc].get("environment"), dict):
                services[entrypoint_svc]["environment"]["FLAG"] = main_flag
            else:
                services[entrypoint_svc]["environment"] = {"FLAG": main_flag}

        # 7. Proje Dizinini Hazırla ve docker-compose.yml Dosyasını Yaz
        proj_dir = os.path.join(COMPOSE_WORK_DIR, project_name)
        os.makedirs(proj_dir, exist_ok=True)
        compose_file_path = os.path.join(proj_dir, "docker-compose.yml")

        with open(compose_file_path, "w") as f:
            yaml.dump(compose_data, f, default_flow_style=False)

        # 8. 'docker compose up -d' ile Ortamı Başlat
        cmd_up = ["docker", "compose", "-p", project_name, "-f", compose_file_path, "up", "-d"]
        try:
            res_up = subprocess.run(cmd_up, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        except subprocess.CalledProcessError as e:
            shutil.rmtree(proj_dir, ignore_errors=True)
            return False, None, f"Docker Compose baslatilamadi: {e.stderr or e.stdout}"

        # 9. Giriş Konteynerinin IP Adresini Tespit Et
        entrypoint_ip = None
        port = int(challenge.container_port or 80)

        for _ in range(20):
            try:
                # Servis konteyner ID'sini al
                cmd_ps = ["docker", "compose", "-p", project_name, "-f", compose_file_path, "ps", "-q", entrypoint_svc]
                cid = subprocess.run(cmd_ps, stdout=subprocess.PIPE, text=True).stdout.strip()
                if cid:
                    cmd_inspect = ["docker", "inspect", cid]
                    inspect_data = json.loads(subprocess.run(cmd_inspect, stdout=subprocess.PIPE, text=True).stdout)
                    if inspect_data:
                        nets = inspect_data[0].get("NetworkSettings", {}).get("Networks", {})
                        if SWARM_NETWORK in nets:
                            entrypoint_ip = nets[SWARM_NETWORK].get("IPAddress")
                        elif nets:
                            # İlk ağın IP'sini al
                            first_net = list(nets.values())[0]
                            entrypoint_ip = first_net.get("IPAddress")
            except Exception:
                pass

            if entrypoint_ip:
                break
            time.sleep(1)

        if not entrypoint_ip:
            entrypoint_ip = project_name

        # 10. Çarpışmasız Dinamik Yerel Alan Adı Üret
        slug = slugify(challenge.name)
        domain = f"{slug}-{identifier}.{DEHLIZ_DOMAIN}"

        # 11. Gateway DNS ve Mikro-Bölümleme Kuralını Ekle
        try:
            requests.post(
                f"{VPN_API_URL}/api/dns",
                json={"domain": domain, "ip": entrypoint_ip, "team_id": team_id},
                timeout=2
            )
        except Exception as e:
            current_app.logger.warning(f"[Dehliz CTF] Compose DNS/Firewall kayit uyarisi: {e}")

        # 12. Veritabanına Kaydet
        timeout_seconds = int(get_config("dehliz:timeout", 7200))  # Compose için varsayılan 2 saat
        expire_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=timeout_seconds)

        instance = DehlizComposeInstance(
            user_id=user_id,
            team_id=team_id,
            challenge_id=challenge.id,
            project_name=project_name,
            entrypoint_ip=entrypoint_ip,
            domain=domain,
            port=port,
            flags=json.dumps(flags_dict),
            start_time=datetime.datetime.utcnow(),
            expire_time=expire_time,
            renew_count=0
        )
        db.session.add(instance)
        db.session.commit()

        return True, instance, "Compose lab ortami basariyla baslatildi."

    @staticmethod
    def destroy_instance(user_id=None, challenge_id=None, instance_id=None, team_id=None):
        query = DehlizComposeInstance.query
        record = None
        if instance_id:
            record = query.filter_by(id=instance_id).first()
        elif team_id and challenge_id:
            record = query.filter_by(team_id=team_id, challenge_id=challenge_id).first()
            if not record and user_id:
                record = query.filter_by(user_id=user_id, challenge_id=challenge_id).first()
        elif user_id and challenge_id:
            record = query.filter_by(user_id=user_id, challenge_id=challenge_id).first()

        if not record:
            return False, "Calisan bir compose ortami bulunamadi."

        # 1. Gateway DNS & Firewall Kaydını Sil
        try:
            requests.delete(
                f"{VPN_API_URL}/api/dns",
                json={"domain": record.domain, "ip": record.entrypoint_ip, "team_id": record.team_id},
                timeout=2
            )
        except Exception as e:
            current_app.logger.warning(f"[Dehliz CTF] Compose DNS/Firewall silme uyarisi: {e}")

        # 2. 'docker compose down -v' Çalıştır
        proj_dir = os.path.join(COMPOSE_WORK_DIR, record.project_name)
        compose_file = os.path.join(proj_dir, "docker-compose.yml")

        if os.path.exists(compose_file):
            cmd_down = ["docker", "compose", "-p", record.project_name, "-f", compose_file, "down", "-v", "--remove-orphans"]
            try:
                subprocess.run(cmd_down, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            except Exception:
                pass
        else:
            # Dizin bulunamazsa proje adıyla doğrudan down dene
            try:
                subprocess.run(["docker", "compose", "-p", record.project_name, "down", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            except Exception:
                pass

        shutil.rmtree(proj_dir, ignore_errors=True)

        db.session.delete(record)
        db.session.commit()
        return True, "Compose ortami basariyla kapatildi ve kaynaklar temizlendi."

    @staticmethod
    def renew_instance(user_id, challenge_id, team_id=None):
        record = ComposeManager.get_user_instance(user_id, challenge_id, team_id=team_id)
        if not record:
            return False, "Yenilenecek aktif bir compose ortami bulunamadi."

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
        """Süresi dolmuş compose ortamlarını periyodik olarak temizler."""
        now = datetime.datetime.utcnow()
        expired = DehlizComposeInstance.query.filter(DehlizComposeInstance.expire_time <= now).all()

        for inst in expired:
            try:
                ComposeManager.destroy_instance(instance_id=inst.id)
            except Exception as e:
                print(f"[Dehliz CTF] Suresi dolan compose silme hatasi ({inst.project_name}): {e}")

        if expired:
            print(f"[Dehliz CTF] {len(expired)} adet suresi dolmus compose labi temizlendi.")
