import os
from flask import Flask, jsonify, request

app = Flask(__name__)

FLAG_FINAL = os.environ.get("FLAG_FINAL", os.environ.get("FLAG", "DEHLIZ{lateral_movement_basariyla_tamamlandi}"))

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "ACME Corp Internal Core Vault API",
        "status": "OPERATIONAL",
        "access": "INTERNAL_NETWORK_ONLY",
        "client_ip": request.remote_addr,
        "endpoints": {
            "/api/health": "Sistem sağlık kontrolü",
            "/api/vault/flag": "Dahili gizli anahtar ve CTF bayrağı",
            "/flag": "Bayrak doğrudan erişim noktası"
        }
    })

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "UP", "internal_ip": request.host})

@app.route("/api/vault/flag", methods=["GET"])
def vault_flag():
    return jsonify({
        "status": "AUTHORIZED",
        "message": "Kurumsal dahili ağdan gelen yetkili istek doğrulandı.",
        "origin_ip": request.remote_addr,
        "vault_id": "VAULT-SEC-9081",
        "flag": FLAG_FINAL
    })

@app.route("/flag", methods=["GET"])
def direct_flag():
    return jsonify({
        "flag": FLAG_FINAL
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
