from CTFd.plugins import (
    register_plugin_assets_directory,
    register_user_page_menu_bar,
    register_admin_plugin_menu_bar,
)
from CTFd.plugins.challenges import CHALLENGE_CLASSES
from .challenge_type import DehlizDockerChallenge
from .api import dehliz_bp
from .scheduler import start_cleaner


def load(app):
    # 1. Veritabanı tablolarını otomatik oluştur (dehliz_containers vb.)
    app.db.create_all()

    # 2. Dehliz Soru Tipini CTFd'ye kaydet
    CHALLENGE_CLASSES["dehliz_docker"] = DehlizDockerChallenge

    # 3. Statik varlıkları (/plugins/ctfd-dehliz/assets) kaydet
    register_plugin_assets_directory(
        app,
        base_path="/plugins/ctfd-dehliz/assets",
        endpoint="plugins.ctfd-dehliz.assets"
    )

    # 4. Blueprint'i Flask uygulamasına kaydet
    app.register_blueprint(dehliz_bp)

    # 5. Üst Menü Çubuklarını Kaydet
    register_user_page_menu_bar(title="🛡️ VPN", route="/vpn")
    register_admin_plugin_menu_bar(title="🛡️ Dehliz CTF", route="/admin/dehliz")

    # 6. Süresi dolan konteynerleri temizleyen arka plan servisini başlat
    start_cleaner(app)

    print("[Dehliz CTF] Yerel Orkestratör ve WireGuard eklentisi başarıyla yüklendi!")
