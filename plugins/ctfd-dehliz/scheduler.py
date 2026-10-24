import time
import threading


def start_cleaner(app):
    def cleaner_loop():
        while True:
            time.sleep(20)
            with app.app_context():
                try:
                    from .docker_manager import DockerManager
                    DockerManager.cleanup_expired_instances()
                except Exception as e:
                    app.logger.warning(f"[Dehliz Cleaner] Temizleme hatasi: {e}")

    thread = threading.Thread(target=cleaner_loop, daemon=True, name="DehlizContainerCleaner")
    thread.start()
