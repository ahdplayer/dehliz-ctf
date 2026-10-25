import os
import datetime
import requests
from flask import Blueprint, request, jsonify, render_template, Response, redirect, url_for
from CTFd.models import Challenges, db
from CTFd.utils.user import get_current_user, authed
from CTFd.utils.decorators import admins_only
from CTFd.utils import get_config, set_config
from .models import DehlizContainer, DehlizChallenge, DehlizComposeChallenge, DehlizComposeInstance
from .docker_manager import DockerManager
from .compose_manager import ComposeManager

VPN_API_URL = os.environ.get("VPN_API_URL", "http://vpn-gateway:5000")

dehliz_bp = Blueprint(
    "ctfd-dehliz",
    __name__,
    template_folder="templates",
    static_folder="assets",
    url_prefix=""
)


def format_user_access(domain, port, ip_address, category="web"):
    host = domain
    port = port or 80
    cat = str(category or "").lower()

    if "web" in cat or port in (80, 443, 3000, 5000, 8000, 8080):
        return (
            f'<div class="mb-2">'
            f'<span class="badge bg-success badge-success text-white px-2 py-1" style="background-color: #28a745 !important; color: #ffffff !important;">🛡️ WireGuard &amp; Yerel DNS</span> '
            f'<small class="text-muted font-weight-bold">({ip_address})</small>'
            f'</div>'
            f'<a target="_blank" class="btn btn-primary btn-sm text-white font-weight-bold shadow-sm" '
            f'href="http://{host}:{port}/">🌐 http://{host}:{port}</a>'
        )
    return (
        f'<div class="mb-2">'
        f'<span class="badge bg-success badge-success text-white px-2 py-1" style="background-color: #28a745 !important; color: #ffffff !important;">🛡️ WireGuard &amp; Yerel DNS</span> '
        f'<small class="text-muted font-weight-bold">({ip_address})</small>'
        f'</div>'
        f'<code class="p-2 border rounded bg-light font-weight-bold text-dark">nc {host} {port}</code>'
    )


def _get_challenge_id():
    req_data = request.get_json(silent=True) or request.form or {}
    raw_id = None
    if isinstance(req_data, dict):
        raw_id = req_data.get("challenge_id")
    if not raw_id and hasattr(request, "args"):
        raw_id = request.args.get("challenge_id")
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


# =========================================================================
# 1. KULLANICI KONTEYNER API'LERİ (Yarışmacı Soru Arayüzü)
# =========================================================================

@dehliz_bp.route("/plugins/ctfd-dehliz/container", methods=["GET"])
def get_container_status():
    if not authed():
        return jsonify({"success": False, "message": "Giriş yapmalısınız."}), 403

    user = get_current_user()
    team_id = user.team_id if user.team_id else user.id
    challenge_id = _get_challenge_id()
    if not challenge_id:
        return jsonify({"success": False, "message": "challenge_id parametresi gereklidir."}), 400

    challenge = Challenges.query.filter_by(id=challenge_id).first()
    if not challenge:
        return jsonify({"success": False, "message": "Soru bulunamadı."}), 404

    now = datetime.datetime.utcnow()

    # 1. Compose Sorusu İse
    if challenge.type == "dehliz_compose":
        inst = ComposeManager.get_user_instance(user.id, challenge_id, team_id=team_id)
        if not inst:
            return jsonify({"success": True, "data": {"status": "stopped"}})
        if inst.expire_time <= now:
            ComposeManager.destroy_instance(user.id, challenge_id, team_id=team_id)
            return jsonify({"success": True, "data": {"status": "stopped"}})
        remaining = int((inst.expire_time - now).total_seconds())
        user_access = format_user_access(inst.domain, inst.port, inst.entrypoint_ip, challenge.category)
        return jsonify({
            "success": True,
            "data": {
                "status": "running",
                "remaining_time": remaining,
                "domain": inst.domain,
                "ip": inst.entrypoint_ip,
                "port": inst.port,
                "renew_count": inst.renew_count,
                "user_access": user_access
            }
        })

    # 2. Standart Tekli Docker Sorusu İse
    container = DockerManager.get_user_container(user.id, challenge_id, team_id=team_id)
    if not container:
        return jsonify({"success": True, "data": {"status": "stopped"}})

    if container.expire_time <= now:
        DockerManager.destroy_instance(user.id, challenge_id, team_id=team_id)
        return jsonify({"success": True, "data": {"status": "stopped"}})

    remaining = int((container.expire_time - now).total_seconds())
    user_access = format_user_access(container.domain, container.port, container.ip_address, challenge.category)

    return jsonify({
        "success": True,
        "data": {
            "status": "running",
            "remaining_time": remaining,
            "domain": container.domain,
            "ip": container.ip_address,
            "port": container.port,
            "renew_count": container.renew_count,
            "user_access": user_access
        }
    })


@dehliz_bp.route("/plugins/ctfd-dehliz/container", methods=["POST"])
def start_container():
    if not authed():
        return jsonify({"success": False, "message": "Giriş yapmalısınız."}), 403

    user = get_current_user()
    team_id = user.team_id if user.team_id else user.id
    challenge_id = _get_challenge_id()
    if not challenge_id:
        return jsonify({"success": False, "message": "challenge_id gereklidir."}), 400

    challenge = Challenges.query.filter_by(id=challenge_id).first()
    if not challenge:
        return jsonify({"success": False, "message": "Soru bulunamadı."}), 404

    # 1. Compose Sorusu Başlatma
    if challenge.type == "dehliz_compose":
        comp_chall = DehlizComposeChallenge.query.filter_by(id=challenge_id).first()
        if not comp_chall:
            return jsonify({"success": False, "message": "Compose soru yapılandırması bulunamadı."}), 404

        ok, inst, msg = ComposeManager.create_instance(user.id, team_id, comp_chall)
        if not ok:
            return jsonify({"success": False, "message": msg}), 400

        remaining = int((inst.expire_time - datetime.datetime.utcnow()).total_seconds())
        user_access = format_user_access(inst.domain, inst.port, inst.entrypoint_ip, challenge.category)

        return jsonify({
            "success": True,
            "message": msg,
            "data": {
                "status": "running",
                "remaining_time": remaining,
                "domain": inst.domain,
                "ip": inst.entrypoint_ip,
                "port": inst.port,
                "user_access": user_access
            }
        })

    # 2. Standart Tekli Docker Sorusu Başlatma
    docker_chall = DehlizChallenge.query.filter_by(id=challenge_id).first()
    if not docker_chall:
        return jsonify({"success": False, "message": "Soru bulunamadı."}), 404

    ok, container, msg = DockerManager.create_instance(user.id, team_id, docker_chall)
    if not ok:
        return jsonify({"success": False, "message": msg}), 400

    remaining = int((container.expire_time - datetime.datetime.utcnow()).total_seconds())
    user_access = format_user_access(container.domain, container.port, container.ip_address, challenge.category)

    return jsonify({
        "success": True,
        "message": msg,
        "data": {
            "status": "running",
            "remaining_time": remaining,
            "domain": container.domain,
            "ip": container.ip_address,
            "port": container.port,
            "user_access": user_access
        }
    })


@dehliz_bp.route("/plugins/ctfd-dehliz/container", methods=["DELETE"])
def stop_container():
    if not authed():
        return jsonify({"success": False, "message": "Giriş yapmalısınız."}), 403

    user = get_current_user()
    team_id = user.team_id if user.team_id else user.id
    challenge_id = _get_challenge_id()
    if not challenge_id:
        return jsonify({"success": False, "message": "challenge_id gereklidir."}), 400

    challenge = Challenges.query.filter_by(id=challenge_id).first()
    if challenge and challenge.type == "dehliz_compose":
        ok, msg = ComposeManager.destroy_instance(user.id, challenge_id, team_id=team_id)
    else:
        ok, msg = DockerManager.destroy_instance(user.id, challenge_id, team_id=team_id)

    return jsonify({"success": ok, "message": msg})


@dehliz_bp.route("/plugins/ctfd-dehliz/container/renew", methods=["POST"])
def renew_container():
    if not authed():
        return jsonify({"success": False, "message": "Giriş yapmalısınız."}), 403

    user = get_current_user()
    team_id = user.team_id if user.team_id else user.id
    challenge_id = _get_challenge_id()
    if not challenge_id:
        return jsonify({"success": False, "message": "challenge_id gereklidir."}), 400

    challenge = Challenges.query.filter_by(id=challenge_id).first()
    if challenge and challenge.type == "dehliz_compose":
        ok, res = ComposeManager.renew_instance(user.id, challenge_id, team_id=team_id)
    else:
        ok, res = DockerManager.renew_instance(user.id, challenge_id, team_id=team_id)

    if not ok:
        return jsonify({"success": False, "message": res}), 400

    return jsonify({"success": True, "remaining_time": res, "message": "Süre başarıyla uzatıldı."})


# =========================================================================
# 2. WIREGUARD VPN KULLANICI SAYFASI (/vpn)
# =========================================================================

@dehliz_bp.route("/vpn", methods=["GET"])
def vpn_index():
    if not authed():
        return redirect(url_for("auth.login", next=request.path))

    user = get_current_user()
    team_id = user.team_id if user.team_id else user.id

    vpn_data = None
    error_msg = None

    try:
        payload = {"team_id": team_id, "user_id": user.id, "username": user.name}
        resp = requests.post(f"{VPN_API_URL}/api/peer", json=payload, timeout=5)
        if resp.status_code in (200, 201):
            vpn_data = resp.json()
        else:
            error_msg = f"VPN sunucusundan beklenmeyen yanıt (HTTP {resp.status_code})"
    except Exception as e:
        error_msg = f"VPN Gateway ile bağlantı kurulamadı: {str(e)}"

    return render_template(
        "vpn.html",
        user=user,
        team_id=team_id,
        vpn_data=vpn_data,
        error_msg=error_msg
    )


@dehliz_bp.route("/vpn/download", methods=["GET"])
def vpn_download():
    if not authed():
        return redirect(url_for("auth.login", next=request.path))

    user = get_current_user()
    team_id = user.team_id if user.team_id else user.id

    try:
        payload = {"team_id": team_id, "user_id": user.id, "username": user.name}
        resp = requests.post(f"{VPN_API_URL}/api/peer", json=payload, timeout=5)
        if resp.status_code in (200, 201):
            data = resp.json()
            config_content = data.get("config", "")
            filename = f"dehliz-takim{team_id}-{user.name}.conf"
            return Response(
                config_content,
                mimetype="application/x-wireguard",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
    except Exception:
        pass

    return redirect(url_for("ctfd-dehliz.vpn_index"))


# =========================================================================
# 3. YÖNETİCİ KONSOLU (/admin/dehliz)
# =========================================================================

@dehliz_bp.route("/admin/dehliz", methods=["GET"])
@admins_only
def admin_dashboard():
    instances = DehlizContainer.query.order_by(DehlizContainer.start_time.desc()).all()
    compose_instances = DehlizComposeInstance.query.order_by(DehlizComposeInstance.start_time.desc()).all()

    # Gateway canlı istatistikleri
    gw_stats = {}
    try:
        res = requests.get(f"{VPN_API_URL}/api/status", timeout=2)
        if res.status_code == 200:
            gw_stats = res.json()
    except Exception:
        gw_stats = {"status": "offline", "error": "Gateway API erişilemez durumda"}

    settings = {
        "timeout": get_config("dehliz:timeout", 3600),
        "renew_time": get_config("dehliz:renew_time", 1800),
        "max_renews": get_config("dehliz:max_renews", 5),
        "max_containers": get_config("dehliz:max_containers", 100),
        "max_compose_instances": get_config("dehliz:max_compose_instances", 30)
    }

    return render_template(
        "admin_dehliz.html",
        instances=instances,
        compose_instances=compose_instances,
        gw_stats=gw_stats,
        settings=settings,
        now=datetime.datetime.utcnow()
    )


@dehliz_bp.route("/admin/dehliz/settings", methods=["POST"])
@admins_only
def admin_save_settings():
    set_config("dehliz:timeout", request.form.get("timeout", 3600))
    set_config("dehliz:renew_time", request.form.get("renew_time", 1800))
    set_config("dehliz:max_renews", request.form.get("max_renews", 5))
    set_config("dehliz:max_containers", request.form.get("max_containers", 100))
    set_config("dehliz:max_compose_instances", request.form.get("max_compose_instances", 30))
    return redirect(url_for("ctfd-dehliz.admin_dashboard"))


@dehliz_bp.route("/admin/dehliz/terminate/<int:container_id>", methods=["POST"])
@admins_only
def admin_terminate_instance(container_id):
    DockerManager.destroy_instance(user_id=None, container_id=container_id)
    return redirect(url_for("ctfd-dehliz.admin_dashboard"))


@dehliz_bp.route("/admin/dehliz/terminate-compose/<int:instance_id>", methods=["POST"])
@admins_only
def admin_terminate_compose_instance(instance_id):
    ComposeManager.destroy_instance(instance_id=instance_id)
    return redirect(url_for("ctfd-dehliz.admin_dashboard"))
