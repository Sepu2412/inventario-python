#!/usr/bin/env bash
# reto8.sh  (Git Bash en Windows)
# Integra inventario-python con los MISMOS contenedores del tutorial.
#
#   bash reto8.sh configurar   # agrega el job a prometheus.yml y reinicia Prometheus
#   bash reto8.sh trafico      # genera trafico en las DOS apps (Java 8080 y Python 8000)
#   bash reto8.sh verificar    # muestra targets de Prometheus e indices de Elasticsearch

REPO="${REPO:-$HOME/ejemplo-grafana-elk}"
PROM="$REPO/monitoring/prometheus/prometheus.yml"
JOB="inventario-python"
PUERTO=8000
N="${N:-30}"

cian(){ printf "\n\033[36m==> %s\033[0m\n" "$1"; }
ok(){   printf "    \033[32m[OK]\033[0m %s\n" "$1"; }
aviso(){ printf "    \033[33m[!]\033[0m %s\n" "$1"; }

verificar(){
  cian "Targets en Prometheus (deben ser 2 y estar en up)"
  curl -s http://localhost:9090/api/v1/targets | grep -o '"job":"[^"]*"\|"health":"[^"]*"' | paste - - | sort -u
  cian "Indices en Elasticsearch (deben salir los de las 2 apps)"
  curl -s "http://localhost:9200/_cat/indices/gestion*,inventario*?v&s=index"
}

case "${1:-}" in
  configurar)
    [ -f "$PROM" ] || { echo "No encuentro $PROM. Usa: REPO=/ruta/al/repo bash reto8.sh configurar"; exit 1; }
    if grep -q "job_name: '$JOB'" "$PROM"; then
      ok "El job $JOB ya estaba en prometheus.yml"
    else
      cp "$PROM" "$PROM.bak"
      cat >> "$PROM" <<EOF

  - job_name: '$JOB'
    metrics_path: '/metrics'
    scrape_interval: 3s
    static_configs:
      - targets: ['host.docker.internal:$PUERTO']
EOF
      ok "Job $JOB agregado (copia de respaldo: prometheus.yml.bak)"
    fi
    cian "prometheus.yml queda asi:"; cat "$PROM"
    cian "Reiniciando Prometheus"
    (cd "$REPO/monitoring" && docker compose restart prometheus)
    sleep 8; verificar ;;
  trafico)
    cian "Generando trafico en las dos aplicaciones ($N rondas)"
    j=0; p=0
    for i in $(seq 1 "$N"); do
      curl -s -f -o /dev/null --max-time 5 http://localhost:8080/api/saludo && j=$((j+1))
      [ $((i % 3)) -eq 0 ] && curl -s -o /dev/null --max-time 5 http://localhost:8080/api/despedida
      curl -s -f -o /dev/null --max-time 5 http://localhost:$PUERTO/api/productos && p=$((p+1))
      curl -s -o /dev/null --max-time 5 http://localhost:$PUERTO/api/comprar
      [ $((i % 4)) -eq 0 ] && curl -s -o /dev/null --max-time 5 http://localhost:$PUERTO/api/error
      [ $((i % 10)) -eq 0 ] && curl -s -o /dev/null --max-time 5 "http://localhost:$PUERTO/api/comprar?producto=impresora"
      sleep 0.5
    done
    [ $j -gt 0 ] && ok "App Java respondio ($j)"   || aviso "La app Java (8080) no respondio: arrancala en IntelliJ"
    [ $p -gt 0 ] && ok "App Python respondio ($p)" || aviso "La app Python (8000) no respondio: python app.py"
    sleep 4; verificar ;;
  verificar) verificar ;;
  *) echo "Uso: bash reto8.sh configurar | trafico | verificar" ;;
esac
