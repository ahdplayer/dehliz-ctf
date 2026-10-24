FROM ctfd/ctfd:3.6.0

USER root

# Dehliz yerel orkestratör bağımlılıkları
RUN pip install --no-cache-dir docker requests

# Dehliz CTF tümleşik eklentisini imaja ekle
COPY plugins/ctfd-dehliz /opt/CTFd/CTFd/plugins/ctfd-dehliz

USER root
