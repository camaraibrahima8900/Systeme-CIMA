FROM quay.io/keycloak/keycloak:24.0 AS builder

ENV KC_DB=mysql
ENV KC_HEALTH_ENABLED=true
ENV KC_METRICS_ENABLED=false

RUN /opt/keycloak/bin/kc.sh build

FROM quay.io/keycloak/keycloak:24.0
COPY --from=builder /opt/keycloak/ /opt/keycloak/

ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start", "--optimized"]
