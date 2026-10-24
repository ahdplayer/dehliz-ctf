FROM docker:latest AS docker-cli
FROM docker/compose-bin:latest AS compose-bin

FROM ctfd/ctfd:3.8.9

USER root

# Docker CLI ve Docker Compose eklentisini ekle
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=compose-bin /docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
RUN chmod +x /usr/local/bin/docker /usr/local/lib/docker/cli-plugins/docker-compose && \
    ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose

# Dehliz yerel orkestratör bağımlılıkları
RUN pip install --no-cache-dir docker requests pyyaml

# Dehliz CTF tümleşik eklentisini imaja ekle
COPY plugins/ctfd-dehliz /opt/CTFd/CTFd/plugins/ctfd-dehliz

USER root
