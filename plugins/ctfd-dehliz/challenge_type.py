import math
from flask import Blueprint
from CTFd.models import db, Flags
from CTFd.plugins.challenges import BaseChallenge
from CTFd.plugins.flags import get_flag_class
from .models import DehlizChallenge, DehlizContainer
from .docker_manager import DockerManager


def calculate_decay(challenge):
    if not challenge.dynamic_score:
        return challenge.initial

    solve_count = (
        challenge.solves
        if hasattr(challenge, "solves")
        else len(challenge.solve_ids) if hasattr(challenge, "solve_ids") else 0
    )
    if solve_count <= 1:
        return challenge.initial

    decay = challenge.decay or 20
    minimum = challenge.minimum or 100
    initial = challenge.initial or 1000

    # Logaritmik puan düşüş formülü
    value = (((minimum - initial) / (decay ** 2)) * (solve_count ** 2)) + initial
    value = math.ceil(value)
    return max(minimum, value)


class DehlizDockerChallenge(BaseChallenge):
    id = "dehliz_docker"
    name = "dehliz_docker"
    templates = {
        "create": "/plugins/ctfd-dehliz/assets/create.html",
        "update": "/plugins/ctfd-dehliz/assets/update.html",
        "view": "/plugins/ctfd-dehliz/assets/view.html",
    }
    scripts = {
        "create": "/plugins/ctfd-dehliz/assets/create.js",
        "update": "/plugins/ctfd-dehliz/assets/update.js",
        "view": "/plugins/ctfd-dehliz/assets/view.js",
    }
    challenge_model = DehlizChallenge

    @classmethod
    def read(cls, challenge):
        challenge = DehlizChallenge.query.filter_by(id=challenge.id).first()
        data = {
            "id": challenge.id,
            "name": challenge.name,
            "value": challenge.value,
            "initial": challenge.initial,
            "decay": challenge.decay,
            "minimum": challenge.minimum,
            "description": challenge.description,
            "category": challenge.category,
            "state": challenge.state,
            "max_attempts": challenge.max_attempts,
            "type": challenge.type,
            "docker_image": challenge.docker_image,
            "container_port": challenge.container_port,
            "memory_limit": challenge.memory_limit,
            "cpu_limit": challenge.cpu_limit,
            "dynamic_score": int(challenge.dynamic_score),
            "type_data": {
                "id": cls.id,
                "name": cls.name,
                "templates": cls.templates,
                "scripts": cls.scripts,
            },
        }
        return data

    @classmethod
    def update(cls, challenge, request):
        data = request.form or request.get_json()
        for attr, value in data.items():
            if attr in ("initial", "minimum", "decay", "cpu_limit"):
                value = float(value)
            elif attr in ("container_port", "value"):
                value = int(value)
            elif attr == "dynamic_score":
                value = bool(int(value))
            setattr(challenge, attr, value)

        if challenge.dynamic_score:
            challenge.value = calculate_decay(challenge)
        else:
            challenge.value = challenge.initial

        db.session.commit()
        return challenge

    @classmethod
    def attempt(cls, challenge, request):
        data = request.form or request.get_json()
        submission = data.get("submission", "").strip()

        # 1. Kullanıcının/Takımın dinamik konteyner bayrağı kontrolü
        from CTFd.utils.user import get_current_user
        user = get_current_user()
        if user:
            container = DockerManager.get_user_container(user.id, challenge.id)
            if container and container.flag and container.flag == submission:
                return True, "Doğru Bayrak!"

        # 2. Standart CTFd bayrak tablosu kontrolü
        flags = Flags.query.filter_by(challenge_id=challenge.id).all()
        for flag in flags:
            try:
                flag_class = get_flag_class(flag.type)
                if flag_class.compare(flag, submission):
                    return True, "Doğru Bayrak!"
            except Exception:
                if flag.content == submission:
                    return True, "Doğru Bayrak!"

        return False, "Hatalı Bayrak."

    @classmethod
    def solve(cls, user, team, challenge, request):
        super().solve(user, team, challenge, request)
        if challenge.dynamic_score:
            challenge.value = calculate_decay(challenge)
            db.session.commit()

        # Bayrak çözüldüğünde sunucu kaynağını boşa çıkarmak için konteyneri otomatik kapat
        try:
            team_id = team.id if team else getattr(user, "team_id", None)
            DockerManager.destroy_instance(user.id, challenge.id, team_id=team_id)
        except Exception:
            pass

    @classmethod
    def delete(cls, challenge):
        # Soru silindiğinde bağlı tüm canlı konteynerleri temizle
        containers = DehlizContainer.query.filter_by(challenge_id=challenge.id).all()
        for c in containers:
            try:
                DockerManager.destroy_instance(c.user_id, challenge.id, container_id=c.id)
            except Exception:
                pass
        super().delete(challenge)
