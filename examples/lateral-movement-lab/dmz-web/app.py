import os
import subprocess
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

FLAG_INITIAL = os.environ.get("FLAG_INITIAL", os.environ.get("FLAG", "DEHLIZ{dmz_web_erisim_basarili}"))

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACME Corp - Ağ Teşhis ve Yönetim Portalı</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {
            background-color: #0b0f19;
            color: #cbd5e1;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
        }
        .navbar {
            background-color: #111827;
            border-bottom: 1px solid #1f2937;
        }
        .card {
            background-color: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        .card-header {
            background-color: #1a2234;
            border-bottom: 1px solid #1f2937;
            font-weight: 600;
        }
        .form-control {
            background-color: #1f2937;
            border: 1px solid #374151;
            color: #f3f4f6;
        }
        .form-control:focus {
            background-color: #111827;
            border-color: #3b82f6;
            color: #ffffff;
            box-shadow: 0 0 0 0.25rem rgba(59, 130, 246, 0.25);
        }
        .terminal {
            background-color: #030712;
            color: #10b981;
            font-family: 'Courier New', Courier, monospace;
            padding: 1.2rem;
            border-radius: 8px;
            border: 1px solid #1f2937;
            white-space: pre-wrap;
            word-break: break-all;
            min-height: 120px;
            max-height: 350px;
            overflow-y: auto;
        }
        .badge-dmz {
            background-color: #f59e0b;
            color: #000;
        }
        .badge-corp {
            background-color: #3b82f6;
            color: #fff;
        }
        .hint-box {
            background-color: rgba(30, 41, 59, 0.7);
            border-left: 4px solid #3b82f6;
            padding: 1rem;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark mb-4">
        <div class="container">
            <span class="navbar-brand d-flex align-items-center gap-2">
                <i class="fa-solid fa-network-wired text-primary"></i>
                <strong>ACME Corp</strong> <span class="text-secondary">|</span> Ağ Tanı & Teşhis Portalı
            </span>
            <div class="d-flex align-items-center gap-2">
                <span class="badge badge-dmz">DMZ Segmenti</span>
                <span class="text-secondary small">{{ client_ip }}</span>
            </div>
        </div>
    </nav>

    <div class="container pb-5">
        <div class="row g-4">
            <!-- Sol Kolon: Ağ Teşhis Formu -->
            <div class="col-lg-7">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span><i class="fa-solid fa-terminal me-2 text-primary"></i>ICMP Ping Teşhis Aracı</span>
                        <span class="badge bg-success">Canlı</span>
                    </div>
                    <div class="card-body">
                        <p class="text-muted small">İç ve dış sunucuların erişilebilirlik ve paket gecikme sürelerini test edin.</p>
                        <form method="POST" action="/" class="mb-3">
                            <div class="input-group">
                                <span class="input-group-text bg-dark border-secondary text-secondary"><i class="fa-solid fa-globe"></i></span>
                                <input type="text" name="target" class="form-control" placeholder="Örn: 127.0.0.1 veya google.com" value="{{ target }}" required>
                                <button type="submit" class="btn btn-primary px-4"><i class="fa-solid fa-play me-1"></i> Çalıştır</button>
                            </div>
                        </form>

                        {% if output %}
                        <div class="mt-4">
                            <label class="form-label text-secondary small fw-bold"><i class="fa-solid fa-microchip me-1"></i>Çıktı Konsolu:</label>
                            <div class="terminal">{{ output }}</div>
                        </div>
                        {% endif %}
                    </div>
                </div>
            </div>

            <!-- Sağ Kolon: Sistem Bilgileri ve Dahili Ağ Haritası -->
            <div class="col-lg-5">
                <div class="card mb-4">
                    <div class="card-header">
                        <i class="fa-solid fa-circle-info me-2 text-info"></i>Sistem & Ağ Durumu
                    </div>
                    <div class="card-body">
                        <ul class="list-unstyled mb-0 small">
                            <li class="mb-2"><strong>Sunucu Adı:</strong> <code class="text-info">{{ hostname }}</code></li>
                            <li class="mb-2"><strong>Dış Erişim (VPN / DMZ):</strong> <span class="badge badge-dmz">dehliz_containers</span></li>
                            <li class="mb-2"><strong>Dahili Ağ (Internal):</strong> <span class="badge badge-corp">internal_corp_net</span></li>
                            <li class="mb-0"><strong>Yönetici:</strong> <code>admin@corp.internal</code></li>
                        </ul>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <i class="fa-solid fa-shield-halved me-2 text-warning"></i>Dahili Bilgi Notu (IT Güvenlik)
                    </div>
                    <div class="card-body small">
                        <div class="hint-box">
                            <p class="mb-1"><strong><i class="fa-solid fa-triangle-exclamation text-warning me-1"></i>Güvenlik Hatırlatması:</strong></p>
                            <p class="text-muted mb-2">
                                DMZ üzerinde bulunan bu sunucu harici VPN kullanıcılarına açıktır. Ancak dahili şirket kasası 
                                (<strong>internal-target:8080</strong>) kesinlikle dış ağa kapalıdır.
                            </p>
                            <p class="mb-0 text-muted">
                                Dahili gizli veriler sadece şirket içi servisteki <code>http://internal-target:8080/api/vault/flag</code> adresinde saklanmaktadır.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    output = ""
    target = ""
    client_ip = request.remote_addr or "127.0.0.1"
    hostname = os.environ.get("HOSTNAME", "web-dmz")

    if request.method == "POST":
        target = request.form.get("target", "").strip()
        if target:
            # Kasıtlı Komut Enjeksiyonu Açığı (Command Injection Vulnerability)
            cmd = f"ping -c 1 -W 1 {target}"
            try:
                raw_out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=6)
                output = raw_out.decode("utf-8", errors="replace")
            except subprocess.CalledProcessError as e:
                output = e.output.decode("utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                output = "Hata: Komut zaman aşımına uğradı (6 saniye)."
            except Exception as e:
                output = f"Hata: {str(e)}"

    return render_template_string(
        HTML_TEMPLATE,
        client_ip=client_ip,
        target=target,
        output=output,
        hostname=hostname
    )

@app.route("/api/ping", methods=["POST"])
def api_ping():
    req = request.get_json(silent=True) or {}
    target = req.get("target", request.form.get("target", "")).strip()
    if not target:
        return jsonify({"status": "error", "message": "Hedef host belirtilmedi."}), 400

    cmd = f"ping -c 1 -W 1 {target}"
    try:
        raw_out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=6)
        output = raw_out.decode("utf-8", errors="replace")
        return jsonify({"status": "success", "output": output})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "output": e.output.decode("utf-8", errors="replace")}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
