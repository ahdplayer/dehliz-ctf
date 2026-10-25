import datetime
from CTFd.models import db, Challenges


class DehlizChallenge(Challenges):
    __mapper_args__ = {"polymorphic_identity": "dehliz_docker"}
    id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    initial = db.Column(db.Integer, default=1000)
    minimum = db.Column(db.Integer, default=100)
    decay = db.Column(db.Integer, default=20)
    docker_image = db.Column(db.String(256), nullable=False)
    container_port = db.Column(db.Integer, default=80)
    memory_limit = db.Column(db.String(32), default="128m")
    cpu_limit = db.Column(db.Float, default=0.5)
    dynamic_score = db.Column(db.Boolean, default=True)

    def __init__(self, *args, **kwargs):
        super(DehlizChallenge, self).__init__(**kwargs)
        self.initial = kwargs.get("initial", kwargs.get("value", 1000))
        self.value = self.initial
        self.minimum = kwargs.get("minimum", 100)
        self.decay = kwargs.get("decay", 20)
        self.docker_image = kwargs.get("docker_image", "")
        self.container_port = int(kwargs.get("container_port", 80))
        self.memory_limit = kwargs.get("memory_limit", "128m")
        self.cpu_limit = float(kwargs.get("cpu_limit", 0.5))
        self.dynamic_score = bool(int(kwargs.get("dynamic_score", 1)))


class DehlizContainer(db.Model):
    __tablename__ = "dehliz_containers"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_id = db.Column(db.Integer, nullable=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    docker_id = db.Column(db.String(128), nullable=False)
    ip_address = db.Column(db.String(64), nullable=True)
    domain = db.Column(db.String(128), nullable=False)
    port = db.Column(db.Integer, default=80)
    flag = db.Column(db.String(256), nullable=True)
    start_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expire_time = db.Column(db.DateTime, nullable=False)
    renew_count = db.Column(db.Integer, default=0)

    challenge = db.relationship("Challenges", foreign_keys=[challenge_id], backref=db.backref("dehliz_containers", cascade="all, delete-orphan"))
    user = db.relationship("Users", foreign_keys=[user_id])


class DehlizComposeChallenge(Challenges):
    __mapper_args__ = {"polymorphic_identity": "dehliz_compose"}
    id = db.Column(
        db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    initial = db.Column(db.Integer, default=1000)
    minimum = db.Column(db.Integer, default=100)
    decay = db.Column(db.Integer, default=20)
    compose_content = db.Column(db.Text, nullable=False)
    entrypoint_service = db.Column(db.String(128), default="")
    container_port = db.Column(db.Integer, default=80)
    total_memory_limit = db.Column(db.String(32), default="1024m")
    dynamic_score = db.Column(db.Boolean, default=True)

    def __init__(self, *args, **kwargs):
        super(DehlizComposeChallenge, self).__init__(**kwargs)
        self.initial = kwargs.get("initial", kwargs.get("value", 1000))
        self.value = self.initial
        self.minimum = kwargs.get("minimum", 100)
        self.decay = kwargs.get("decay", 20)
        self.compose_content = kwargs.get("compose_content", "")
        self.entrypoint_service = kwargs.get("entrypoint_service", "")
        self.container_port = int(kwargs.get("container_port", 80))
        self.total_memory_limit = kwargs.get("total_memory_limit", "1024m")
        self.dynamic_score = bool(int(kwargs.get("dynamic_score", 1)))


class DehlizComposeInstance(db.Model):
    __tablename__ = "dehliz_compose_instances"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_id = db.Column(db.Integer, nullable=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)
    project_name = db.Column(db.String(128), nullable=False)
    entrypoint_ip = db.Column(db.String(64), nullable=True)
    domain = db.Column(db.String(128), nullable=False)
    port = db.Column(db.Integer, default=80)
    flags = db.Column(db.Text, nullable=True)  # JSON formatında dinamik bayraklar
    start_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expire_time = db.Column(db.DateTime, nullable=False)
    renew_count = db.Column(db.Integer, default=0)

    challenge = db.relationship("Challenges", foreign_keys=[challenge_id], backref=db.backref("dehliz_compose_instances", cascade="all, delete-orphan"))
    user = db.relationship("Users", foreign_keys=[user_id])

