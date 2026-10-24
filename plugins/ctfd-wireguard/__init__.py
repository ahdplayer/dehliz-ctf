import os
import requests
from flask import Blueprint, render_template, Response, redirect, url_for, request
from CTFd.plugins import register_user_page_menu_bar
from CTFd.utils.user import get_current_user, authed

VPN_API_URL = os.environ.get("VPN_API_URL", "http://vpn-gateway:5000")


def load(app):
    blueprint = Blueprint(
        "ctfd-wireguard",
        __name__,
        template_folder="templates",
        url_prefix="/vpn"
    )

    @blueprint.route("", methods=["GET"])
    def vpn_index():
        if not authed():
            return redirect(url_for("auth.login", next=request.path))

        user = get_current_user()
        team_id = user.team_id if user.team_id else user.id

        # VPN Gateway'den dinamik config iste
        vpn_data = None
        error_msg = None

        try:
            payload = {
                "team_id": team_id,
                "user_id": user.id,
                "username": user.name
            }
            resp = requests.post(f"{VPN_API_URL}/api/peer", json=payload, timeout=5)
            if resp.status_code in (200, 201):
                vpn_data = resp.json()
            else:
                error_msg = f"VPN sunucusundan beklenmeyen yanıt alındı (HTTP {resp.status_code})"
        except Exception as e:
            error_msg = f"VPN Gateway ile bağlantı kurulamadı: {str(e)}"

        return render_template(
            "vpn.html",
            user=user,
            team_id=team_id,
            vpn_data=vpn_data,
            error_msg=error_msg
        )

    @blueprint.route("/download", methods=["GET"])
    def vpn_download():
        if not authed():
            return redirect(url_for("auth.login", next=request.path))

        user = get_current_user()
        team_id = user.team_id if user.team_id else user.id

        try:
            payload = {
                "team_id": team_id,
                "user_id": user.id,
                "username": user.name
            }
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

        return redirect(url_for("ctfd-wireguard.vpn_index"))

    app.register_blueprint(blueprint)

    # CTFd Üst Menü Çubuğuna "🛡️ VPN" Butonu Ekle
    register_user_page_menu_bar(title="🛡️ VPN", route="/vpn")
    print("[Dehliz CTF WireGuard] Eklenti başarıyla yüklendi!")
