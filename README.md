# Projet Azru : Jumeau Numérique & Gestion Énergétique (MPC)

Azru est un prototype (MVP) de **système de gestion énergétique résidentielle autonome** basé sur le concept de Jumeau Numérique (Digital Twin). Il simule et contrôle la thermique d'un bâtiment en optimisant la commande d'une vanne de chauffage via un algorithme **MPC (Model Predictive Control)** connecté aux tarifs de l'électricité (EDF Tempo) et aux prévisions météorologiques.

Le projet est conçu pour fonctionner en Edge-Computing (ex: Raspberry Pi 4) et repose sur une architecture de microservices **entièrement asynchrone** pour garantir des performances optimales.

---

## 🏗️ Architecture et Stack Technique

*   **Backend Core** : `Python 3.10` / `FastAPI` (100% Asynchrone avec l'Event-Loop `asyncio`).
*   **Contrôle Avancé (MPC)** : Solveur mathématique `GEKKO` (déporté dans son propre `Thread` pour ne pas bloquer l'API).
*   **Base de Données Time-Series** : `InfluxDB v2` (Connecteur `influxdb-client-async`).
*   **Event Bus / Message Broker** : `Eclipse Mosquitto` (MQTT) pour la communication inter-services.
*   **Visualisation** : `Grafana` (Connecté directement à InfluxDB).
*   **Calculs Physiques** : Librairie de simulation `RC_BuildingSimulator` (Modèle équivalent 5R1C).

### Refonte Asynchrone (Anti-Freeze)
Au cœur du moteur FastAPI, les dépendances réseaux (requêtes API Tempo via `httpx`), les écritures InfluxDB massives (`write_api`) et le solveur prédictif MPC (`m.solve()`) interagissent sans jamais bloquer la file d'attente du serveur web. Le lien avec MQTT se fait via un système de **Callbacks d'événements** désengorgeant le parseur de logs.

---

## 🚀 1. Mode "Temps-Réel" (Docker)
C'est le mode destiné au déploiement en production ou via un simulateur en temps-réel (qui publie virtuellement des événements MQTT seconde par seconde).

### Démarrage Rapide

1. Assurez-vous d'avoir Docker et Docker-Compose installés.
2. Démarrez l'infrastructure complète (Backend, DB, Broker, Dashboard, Sensor-Simulator) :
```bash
docker-compose up -d --build
```
3. Vérifiez les conteneurs : `docker-compose ps`

### Accès aux Services
*   **Swagger API (Azru Core)** : [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Grafana** : [http://localhost:3000](http://localhost:3000) *(admin / admin)*
*   **InfluxDB UI** : [http://localhost:8086](http://localhost:8086)

---

## ⚡ 2. Mode "Simulation Batch" (Hors-Ligne)
Destiné aux Data-Scientists et aux tests de scénarios, ce mode **bypass totalement MQTT et Docker** pour simuler des journées entières en quelques secondes. Il écrit directement les prédictions thermiques et économiques dans InfluxDB pour être étudiées dans Grafana.

Le script `run_simulation.py` orchestre la simulation rapide.

### Prérequis Locaux
Si vous tournez ce script en local (hors Docker), assurez-vous d'avoir un environnement virtuel avec les dépendances :
```bash
pip install -r requirements.txt
```
*(Le script pointe automatiquement vers `localhost:8086` si InfluxDB tourne via Docker en arrière-plan).*

### Commandes Utiles

**Simuler plusieurs jours en Mode MPC (Smart Heating) :**
```bash
python run_simulation.py --start 2026-02-01T00:00:00 --end 2026-02-05T00:00:00 --mode mpc
```

**Simuler en Mode Manuel (Thermostat Bête d'ouvrier) :**
```bash
python run_simulation.py --start 2026-02-01T00:00:00 --end 2026-02-05T00:00:00 --mode manual
```

**Purger intégralement la base InfluxDB avant un run :**
```bash
python run_simulation.py --reset --start 2026-02-01T00:00:00 --end 2026-02-02T00:00:00 --mode mpc
```
*(Vous pouvez aussi utiliser l'option `--reset` toute seule).*

---

## 🧠 Services Intelligents

### 1. Le Service MPC (`mpc_service.py`)
Le Model Predictive Control minimise la fonction de coût financier du chauffage sur un horizon de 24h.
- **Entrées** : Météo (Sinusoïdale/Mock), Prix Tempo EDF de l'API web (`Bleu/Blanc/Rouge`), Température initiale lue depuis la TSDB.
- **Contraintes** : `T_min = 19°C` et `T_max = 28°C`. La surchauffe inutile est pénalisée de façon **asymétrique** pour éviter d'exploiter la chaleur au lancement de la maquette physique.
- **Sortie** : Une commande d'ouverture de vanne (`valve_position` entre 0 et 100%).

### 2. Le Contrôleur Manuel (`manual_controller.py`)
Utilisé en outil de comparaison (Baseline/A-B Testing). Il allume la vanne à 100% en dessous de 19.5°C et la coupe à 0% au-dessus de 20.5°C, sans anticiper les chocs tarifaires.

---

## 📂 Structure du Répertoire
```
/
├── app/                  # Application FastAPI Core
│   ├── digital_twin/     # Moteur Physique (RC_Simulator) et Scénarios Météo
│   ├── models/           # Modèles Pydantic / Données
│   └── services/         # Logique métier Async (MPC, MQTT, Manual, Influx)
├── mosquitto/            # Conf Broker
├── run_simulation.py     # L'outil CLI de simulation Batch hyper-accélérée
├── docker-compose.yml    # Le déploiement
└── requirements.txt      # Dépendances Python
```
