FROM quay.io/openstack.kolla/horizon:2024.1-ubuntu-jammy

USER root

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY start-horizon.sh /usr/local/bin/start-horizon.sh
RUN chmod +x /usr/local/bin/start-horizon.sh

ENTRYPOINT ["/usr/local/bin/start-horizon.sh"]
