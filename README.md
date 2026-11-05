# inventario-python

Aplicación Flask (Python) para el **Reto 8 – Monitoreo de una aplicación propia con Grafana y ELK** (Gestión de la Configuración, Universidad de Medellín).

| Elemento | Valor |
|---|---|
| Lenguaje / framework | Python 3 + Flask |
| Nombre (`application`) | `inventario-python` |
| Puerto | `8000` |
| Métricas | `/metrics` con `prometheus_client` |
| Logs | JSON por TCP a Logstash `localhost:5001` (handler propio con `logging` + `socket`) |
| Job en Prometheus | `inventario-python` |
| Índice en Elasticsearch | `inventario-python-AAAA.MM.DD` |

## Endpoints

| Ruta | Log que genera |
|---|---|
| `GET /api/productos` | INFO "Consultando inventario" |
| `GET /api/comprar` | INFO "Venta realizada: …" (o ERROR si `?producto=` no existe) |
| `GET /api/error` | ERROR "Error procesando el pago: pasarela no disponible" |
| `GET /metrics` | Métricas en formato Prometheus |

## Métricas propias

- `inventario_http_requests_total{endpoint,method,status}`: peticiones HTTP
- `inventario_http_request_duration_seconds` (histograma): latencia por endpoint
- `inventario_ventas_total{producto}`: unidades vendidas
- `inventario_errores_total{tipo}`: errores de negocio
- `inventario_stock_unidades{producto}`: stock disponible

## Cómo ejecutarla

```bash
python -m pip install -r requirements.txt
python app.py
```

Integración con los contenedores del repositorio `ejemplo-grafana-elk`:

```bash
bash reto8.sh configurar   # agrega el job a monitoring/prometheus/prometheus.yml y reinicia Prometheus
bash reto8.sh trafico      # genera tráfico en la app Java (8080) y en esta (8000)
bash reto8.sh verificar    # targets de Prometheus e índices de Elasticsearch
```

Dashboard de Grafana: **Dashboards → New → Import → Upload dashboard JSON file** → `dashboard-inventario-python.json` → elegir la fuente Prometheus.
