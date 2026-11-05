"""
inventario-python
Aplicacion Flask de ejemplo para el Reto 8 (Gestion de la Configuracion - UdeM).
 - Metricas en formato Prometheus en /metrics (libreria prometheus_client)
 - Logs en JSON enviados por TCP a Logstash (localhost:5001), un objeto por linea
"""
import json
import logging
import random
import socket
import threading
import time
from datetime import datetime, timezone

from flask import Flask, Response, jsonify, request
from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               generate_latest)

APP_NAME = "inventario-python"
PORT = 8000
LOGSTASH_HOST, LOGSTASH_PORT = "localhost", 5001


# ---------------------------------------------------------------- logs -> Logstash
class LogstashTcpHandler(logging.Handler):
    """Envia cada log como una linea JSON por TCP. Si Logstash no esta, reintenta luego."""

    def __init__(self, host, port):
        super().__init__()
        self.host, self.port = host, port
        self.sock = None
        self._sock_lock = threading.Lock()

    def _conectar(self):
        s = socket.create_connection((self.host, self.port), timeout=2)
        s.settimeout(2)
        return s

    def emit(self, record):
        evento = {
            "@timestamp": datetime.fromtimestamp(record.created, timezone.utc)
                          .isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "application": APP_NAME,
            "logger_name": record.name,
            "thread_name": record.threadName,
        }
        evento.update(getattr(record, "extra_fields", {}))
        linea = (json.dumps(evento, ensure_ascii=False) + "\n").encode("utf-8")
        with self._sock_lock:
            for _ in range(2):  # un reintento si la conexion se cayo
                try:
                    if self.sock is None:
                        self.sock = self._conectar()
                    self.sock.sendall(linea)
                    return
                except OSError:
                    if self.sock:
                        self.sock.close()
                    self.sock = None


log = logging.getLogger(APP_NAME)
log.setLevel(logging.INFO)
consola = logging.StreamHandler()
consola.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s"))
log.addHandler(consola)
log.addHandler(LogstashTcpHandler(LOGSTASH_HOST, LOGSTASH_PORT))


def info(msg, **campos):
    log.info(msg, extra={"extra_fields": campos})


def error(msg, **campos):
    log.error(msg, extra={"extra_fields": campos})


# ---------------------------------------------------------------- metricas
PETICIONES = Counter("inventario_http_requests_total", "Peticiones HTTP recibidas",
                     ["endpoint", "method", "status"])
LATENCIA = Histogram("inventario_http_request_duration_seconds", "Duracion de las peticiones",
                     ["endpoint"], buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2))
VENTAS = Counter("inventario_ventas_total", "Unidades vendidas", ["producto"])
ERRORES = Counter("inventario_errores_total", "Errores de negocio", ["tipo"])
STOCK = Gauge("inventario_stock_unidades", "Unidades disponibles", ["producto"])
INICIO = Gauge("inventario_inicio_timestamp_seconds", "Momento de arranque (epoch)")

stock = {"teclado": 50, "mouse": 80, "monitor": 20, "audifonos": 35}
for p, u in stock.items():
    STOCK.labels(p).set(u)
INICIO.set(time.time())

app = Flask(__name__)


@app.before_request
def _inicio():
    request._t0 = time.perf_counter()


@app.after_request
def _fin(resp):
    if request.path != "/metrics":
        ep = request.url_rule.rule if request.url_rule else "desconocido"
        LATENCIA.labels(ep).observe(time.perf_counter() - request._t0)
        PETICIONES.labels(ep, request.method, str(resp.status_code)).inc()
    return resp


# ---------------------------------------------------------------- endpoints
@app.get("/")
def inicio():
    return jsonify(app=APP_NAME, endpoints=["/api/productos", "/api/comprar",
                                            "/api/error", "/metrics"])


@app.get("/api/productos")
def productos():
    time.sleep(random.uniform(0.005, 0.05))
    info("Consultando inventario", endpoint="/api/productos", productos=len(stock))
    return jsonify(stock)


@app.get("/api/comprar")
def comprar():
    producto = request.args.get("producto") or random.choice(list(stock))
    time.sleep(random.uniform(0.02, 0.2))
    if producto not in stock:
        ERRORES.labels("producto_inexistente").inc()
        error(f"Producto inexistente: {producto}", endpoint="/api/comprar")
        return jsonify(error="producto inexistente"), 404
    if stock[producto] == 0:
        stock[producto] = 50  # reabastece para que la demo no se quede sin stock
        info(f"Reabasteciendo {producto}", endpoint="/api/comprar")
    stock[producto] -= 1
    STOCK.labels(producto).set(stock[producto])
    VENTAS.labels(producto).inc()
    info(f"Venta realizada: {producto}", endpoint="/api/comprar", producto=producto)
    return jsonify(vendido=producto, quedan=stock[producto])


@app.get("/api/error")
def falla():
    time.sleep(random.uniform(0.1, 0.4))
    ERRORES.labels("pago_rechazado").inc()
    error("Error procesando el pago: pasarela no disponible", endpoint="/api/error")
    return jsonify(error="pago rechazado"), 500


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    info(f"Iniciando {APP_NAME} en el puerto {PORT}")
    # 0.0.0.0 para que Prometheus (dentro de Docker) pueda llegar a la app
    app.run(host="0.0.0.0", port=PORT)
