FROM alpine:3.19

RUN apk add --no-cache \
    python3 \
    py3-pip \
    wireguard-tools \
    iproute2 \
    curl \
    bind-tools \
    iptables \
    docker-cli \
    bash

WORKDIR /app
COPY . /app

ENV PYTHONUNBUFFERED=1

CMD ["python3", "/app/tests/test_cyber_range.py"]
