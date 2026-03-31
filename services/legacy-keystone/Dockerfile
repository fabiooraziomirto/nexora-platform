FROM quay.io/openstack.kolla/keystone:2024.1-ubuntu-jammy

USER root

COPY bootstrap-keystone.sh /usr/local/bin/bootstrap-keystone.sh
RUN chmod +x /usr/local/bin/bootstrap-keystone.sh

ENTRYPOINT ["/usr/local/bin/bootstrap-keystone.sh"]
