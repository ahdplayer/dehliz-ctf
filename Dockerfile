FROM ctfd/ctfd:3.6.0

USER root

# Dehliz WireGuard ve Whale eklentilerini imaja ekle
COPY plugins/ctfd-whale /opt/CTFd/CTFd/plugins/ctfd-whale
COPY plugins/ctfd-wireguard /opt/CTFd/CTFd/plugins/ctfd-wireguard

# Whale eklentisi bağımlılıklarını kur
RUN pip install --no-cache-dir -r /opt/CTFd/CTFd/plugins/ctfd-whale/requirements.txt

# API token kimlik doğrulamasında dosya yükleme (multipart/form-data) desteğini etkinleştir
RUN sed -i 's/if token and request.content_type == "application\/json":/if token:/' /opt/CTFd/CTFd/utils/initialization/__init__.py

USER root
