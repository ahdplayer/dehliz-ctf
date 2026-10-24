import os
from flask import Flask, request, render_template_string

app = Flask(__name__)

FLAG = os.environ.get("FLAG", "DEHLIZ{ornek_bayrak_basariyla_cozuldu}")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Dehliz Örnek Soru</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .card { background: #1e293b; border: 1px solid #334155; padding: 2rem; border-radius: 1rem; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); max-width: 500px; text-align: center; }
        h1 { color: #10b981; margin-top: 0; }
        code { background: #0f172a; padding: 0.2rem 0.4rem; border-radius: 0.25rem; font-family: monospace; color: #38bdf8; }
        .ip-info { margin-top: 1rem; font-size: 0.9rem; color: #94a3b8; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🛡️ Tebrikler!</h1>
        <p>Dehliz CTF WireGuard tüneli üzerinden bu izole konteynere başarıyla eriştiniz.</p>
        <div class="ip-info">
            İstemci IP Adresiniz: <code>{{ client_ip }}</code><br>
            Sunucu Alan Adı: <code>{{ host_name }}</code>
        </div>
        <hr style="border-color: #334155; margin: 1.5rem 0;">
        <p>Soru Bayrağı: <code>{{ flag }}</code></p>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    client_ip = request.remote_addr
    host_name = request.host
    return render_template_string(HTML_TEMPLATE, client_ip=client_ip, host_name=host_name, flag=FLAG)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
