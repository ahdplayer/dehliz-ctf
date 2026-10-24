FROM alpine:3.20

# Temel paketler: WireGuard, iptables, iproute2, dnsmasq, python3
RUN apk add --no-cache \
    wireguard-tools \
    iptables \
    iproute2 \
    bash \
    python3 \
    dnsmasq \
    curl

WORKDIR /etc/wireguard

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY vpn_manager.py /usr/local/bin/vpn_manager.py

RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh \
    && sed -i 's/\r$//' /usr/local/bin/vpn_manager.py \
    && chmod +x /usr/local/bin/entrypoint.sh \
    && chmod +x /usr/local/bin/vpn_manager.py

EXPOSE 51820/udp
EXPOSE 53/udp
EXPOSE 53/tcp
EXPOSE 5000/tcp

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
