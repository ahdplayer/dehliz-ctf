from CTFd.plugins import (
    register_plugin_assets_directory,
    register_user_page_menu_bar,
    register_admin_plugin_menu_bar,
)
from CTFd.plugins.challenges import CHALLENGE_CLASSES, BaseChallenge
from .challenge_type import DehlizDockerChallenge
from .api import dehliz_bp
from .scheduler import start_cleaner


def install_solve_auto_cleanup():
    """Tüm CTFd soru tiplerinde (standard, dynamic, dehliz_docker vb.) soru çözüldüğünde konteyneri otomatik kapatır."""
    original_solve = BaseChallenge.solve

    @classmethod
    def auto_cleanup_solve(cls, user, team, challenge, request):
        res = original_solve(user, team, challenge, request)
        try:
            from .docker_manager import DockerManager
            from CTFd.utils import get_config

            auto_destroy = str(get_config("dehliz:destroy_on_solve", "true")).lower() in ("true", "1")
            if auto_destroy:
                team_id = team.id if team else getattr(user, "team_id", None)
                ok, msg = DockerManager.destroy_instance(
                    user_id=user.id,
                    challenge_id=challenge.id,
                    team_id=team_id
                )
                if ok:
                    print(f"[Dehliz CTF] Soru {challenge.id} çözüldü ({user.name} - Takım {team_id}). Canlı konteyner otomatik kapatıldı.")
        except Exception as e:
            print(f"[Dehliz CTF] Çözülen konteyneri kapatma hatası: {e}")
        return res

    BaseChallenge.solve = auto_cleanup_solve


def load(app):
    # 1. Veritabanı tablolarını otomatik oluştur (dehliz_containers vb.)
    app.db.create_all()

    # 2. Dehliz Soru Tipini CTFd'ye kaydet
    CHALLENGE_CLASSES["dehliz_docker"] = DehlizDockerChallenge

    # 3. Tüm soru tipleri için çözüldüğünde otomatik kapatma kancasını tak
    install_solve_auto_cleanup()

    # 4. Statik varlıkları (/plugins/ctfd-dehliz/assets) kaydet
    register_plugin_assets_directory(
        app,
        base_path="/plugins/ctfd-dehliz/assets",
        endpoint="plugins.ctfd-dehliz.assets"
    )

    # 5. Blueprint'i Flask uygulamasına kaydet
    app.register_blueprint(dehliz_bp)

    # 6. Üst Menü Çubuklarını Kaydet
    register_user_page_menu_bar(title="🛡️ VPN", route="/vpn")
    register_admin_plugin_menu_bar(title="🛡️ Dehliz CTF", route="/admin/dehliz")

    # 7. Süresi dolan konteynerleri temizleyen arka plan servisini başlat
    start_cleaner(app)

    print("[Dehliz CTF] Yerel Orkestratör ve WireGuard eklentisi başarıyla yüklendi!")
