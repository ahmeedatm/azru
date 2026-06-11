# Azru: Digital Twin & Energy Management (MPC)

Azru is an MVP of an **autonomous residential energy management system** built on the Digital Twin concept. It simulates and controls a building's thermal behaviour by optimising a heating valve's command via a **Model Predictive Control (MPC)** algorithm connected to electricity tariffs (EDF Tempo) and weather forecasts.

The project is designed to run on Edge Computing hardware (e.g., Raspberry Pi 4) and relies on a **fully asynchronous** microservices architecture for optimal performance.

---

## 🏗️ Architecture & Tech Stack

*   **Backend Core**: `Python 3.10` / `FastAPI` (100% async on the `asyncio` event loop).
*   **Advanced Control (MPC)**: `GEKKO` mathematical solver (offloaded to its own `Thread` so it never blocks the API).
*   **Time-Series Database**: `InfluxDB v2` (via the `influxdb-client-async` connector).
*   **Event Bus / Message Broker**: `Eclipse Mosquitto` (MQTT) for inter-service communication.
*   **Visualisation**: `Grafana` (wired directly to InfluxDB).
*   **Physics Engine**: `RC_BuildingSimulator` library (5R1C equivalent thermal model).

### Async Redesign (Anti-Freeze)
At the core of the FastAPI engine, network calls (Tempo API via `httpx`), heavy InfluxDB writes (`write_api`), and the MPC solver (`m.solve()`) never block the request queue. MQTT integration uses an **event callback** system that keeps the log parser from backing up.

---

## 🚀 1. "Real-Time" Mode (Docker)
The deployment mode for production or for a real-time simulator that publishes virtual MQTT events second by second.

### Quick Start

1. Make sure Docker and Docker Compose are installed.
2. Bring up the full infrastructure (Backend, DB, Broker, Dashboard, Sensor-Simulator):
```bash
docker-compose up -d --build
```
3. Check the containers: `docker-compose ps`

### Service Endpoints
*   **Swagger API (Azru Core)**: [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Grafana**: [http://localhost:3000](http://localhost:3000) *(admin / admin)*
*   **InfluxDB UI**: [http://localhost:8086](http://localhost:8086)

---

## ⚡ 2. "Batch Simulation" Mode (Offline)
Aimed at data scientists and scenario testing, this mode **bypasses MQTT and Docker entirely** and simulates whole days in a few seconds. It writes thermal and economic predictions directly into InfluxDB so you can explore them in Grafana.

The `run_simulation.py` script orchestrates the fast simulation.

### Local Prerequisites
If you run the script locally (outside Docker), set up a virtual environment with the dependencies:
```bash
pip install -r requirements.txt
```
*(The script automatically targets `localhost:8086` if InfluxDB is running via Docker in the background.)*

### Useful Commands

**Simulate several days in MPC mode (Smart Heating):**
```bash
python run_simulation.py --start 2026-02-01T00:00:00 --end 2026-02-05T00:00:00 --mode mpc
```

**Simulate in Manual mode (Dumb Thermostat baseline):**
```bash
python run_simulation.py --start 2026-02-01T00:00:00 --end 2026-02-05T00:00:00 --mode manual
```

**Wipe InfluxDB clean before a run:**
```bash
python run_simulation.py --reset --start 2026-02-01T00:00:00 --end 2026-02-02T00:00:00 --mode mpc
```
*(You can also use `--reset` on its own.)*

---

## 🧠 Smart Services

### 1. The MPC Service (`mpc_service.py`)
Model Predictive Control minimises the heating cost function over a 24-hour horizon.
- **Inputs**: Weather (sinusoidal / mock), EDF Tempo tariff from the web API (`Blue/White/Red`), initial temperature read from the TSDB.
- **Constraints**: `T_min = 19°C` and `T_max = 28°C`. Unnecessary overheating is penalised **asymmetrically** to prevent the solver from exploiting heat carry-over when the physical model boots up.
- **Output**: A valve opening command (`valve_position` between 0 and 100%).

### 2. The Manual Controller (`manual_controller.py`)
Used as the comparison baseline (A/B testing). It opens the valve to 100% below 19.5°C and closes it at 0% above 20.5°C, without anticipating tariff spikes.

---

## 📂 Repository Layout
```
/
├── app/                  # FastAPI core application
│   ├── digital_twin/     # Physics engine (RC_Simulator) and weather scenarios
│   ├── models/           # Pydantic models / data structures
│   └── services/         # Async business logic (MPC, MQTT, Manual, Influx)
├── mosquitto/            # Broker configuration
├── run_simulation.py     # Fast batch-simulation CLI
├── docker-compose.yml    # Deployment
└── requirements.txt      # Python dependencies
```

---

🇫🇷 La version française se trouve dans [README.md](./README.md).
