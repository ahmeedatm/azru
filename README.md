# Système de Gestion Énergétique Résidentielle (IoT Edge)

Ce projet est un MVP pour la gestion énergétique résidentielle autonome sur Raspberry Pi 4. Il utilise une architecture de microservices conteneurisés pour collecter des données via MQTT, les stocker dans InfluxDB et les visualiser avec Grafana. 

## Architecture

*   **Orchestration** : Docker & Docker Compose
*   **Backend** : Python 3.10+ avec FastAPI (Asynchrone)
*   **Base de données** : InfluxDB v2 (Time-Series)
*   **Communication** : MQTT (Eclipse Mosquitto) + Zigbee2MQTT
*   **Visualisation** : Grafana

## Structure du Projet

```
/
├── app/                 # Code source Python (FastAPI)
│   ├── config.py        # Configuration
│   ├── main.py          # Point d'entrée
│   └── services/        # Services (MQTT, InfluxDB)
├── mosquitto/           # Configuration Mosquitto
├── zigbee2mqtt/         # Données Zigbee2MQTT
├── docker-compose.yml   # Orchestration des services
└── .env                 # Variables d'environnement (Secrets)
```

## Prérequis

*   Raspberry Pi 4 (ou tout système Linux/Mac compatible)
*   Docker & Docker Compose installés
*   Clé Zigbee (pour Zigbee2MQTT) connectée au port approprié (défaut: `/dev/ttyACM0`)

## Modes de Fonctionnement (Hardware vs Simulation)

Ce projet supporte deux modes via la variable `COMPOSE_PROFILES` dans le fichier `.env` :

1.  **Mode Simulation (`COMPOSE_PROFILES=simulation`)** :
    *   Lance un script Python qui génère des données de capteurs factices.
    *   **Aucun matériel Zigbee requis**.
    *   Idéal pour le développement et les tests.

2.  **Mode Hardware (`COMPOSE_PROFILES=hardware`)** :
    *   Lance le service `zigbee2mqtt`.
    *   **Nécessite un dongle Zigbee** connecté au port USB (par défaut `/dev/ttyACM0`).
    *   Pour le déploiement réel.

## Installation & Démarrage

1.  **Configurer l'environnement** :
    Copiez ou renommez le fichier `.env` et choisissez votre mode :
    ```bash
    # Exemple pour tester sans matériel :
    COMPOSE_PROFILES=simulation
    ```
    
2.  **Configurer le Dongle Zigbee (Si Mode Hardware)** :
    Vérifiez que votre clé Zigbee est bien sur `/dev/ttyACM0` (voir `docker-compose.yml`).
    
3.  **Lancer les services** :
    ```bash
    docker-compose up -d --build
    ```
    Docker ne lancera que les services associés au profil choisi (plus les services communs comme Mosquitto, InfluxDB, Grafana).

4.  **Vérifier que tout tourne** :
    ```bash
    docker-compose ps
    ```

## Accès aux Interfaces

*   **Backend API** : [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)
*   **Grafana** : [http://localhost:3000](http://localhost:3000) (Login: admin/admin par défaut ou voir `.env`)
*   **InfluxDB UI** : [http://localhost:8086](http://localhost:8086) (Login avec user/pass du `.env`)
*   **Zigbee2MQTT** : Interface frontend non activée par défaut, mais accessible via MQTT.

## Développement

Le dossier `app/` est monté en volume dans le conteneur `app-backend`. Toute modification de code redémarrera automatiquement le serveur (si configuré avec reload, sinon redémarrer le conteneur).
