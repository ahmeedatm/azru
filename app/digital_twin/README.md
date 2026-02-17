# Digital Twin Simulator 🏠

Ce module fournit un **Jumeau Numérique** de votre logement pour tester le système MPC dans des conditions réalistes et reproductibles.

## Architecture

Le simulateur est composé de 3 blocs principaux :

1.  **`physics.py` (Moteur Physique)** : Implémente le modèle thermique R1C1. Il calcule la température minute par minute en fonction des pertes (murs), des apports solaires (fenêtres), et du chauffage.
2.  **`loader.py` (Scénarios)** : Charge des fichiers JSON (dans `scenarios/`) qui définissent la météo (température extérieure, nuages) et les tarifs d'électricité sur plusieurs jours.
3.  **`simulator.py` (Orchestrateur)** :
    *   Fait avancer le temps (accéléré, ex: 1sec réelle = 1min simulée).
    *   **Maître du Temps** : Publie l'heure virtuelle sur MQTT (`home/sys/clock`) pour synchroniser tout le système.
    *   Publie les données capteurs (`home/sensors/...`) et écoute les commandes de vanne (`home/.../valve/set`).

## Démarrage Rapide

Le simulateur est packagé avec le reste de l'application via Docker.

### 1. Lancer la simulation
```bash
docker-compose up -d --build
```
Cela lance le conteneur `iot_simulator` qui exécute par défaut le scénario `scenario_neige.json`.

### 2. Vérifier que ça tourne
Regardez les logs pour voir le temps avancer et la température évoluer :
```bash
docker logs -f iot_simulator
```
*Vous devriez voir des lignes `Sim 08:00 | T_int=19.5 | ...`*

### 3. Tester la réaction du MPC
Ouvrez un autre terminal et regardez les logs du Backend MPC. Vous devez voir qu'il reçoit l'heure simulée :
```bash
docker logs -f iot_backend | grep "clock"
```

### 4. Modifier le Scénario
Pour tester un autre climat (ex: Soleil), modifiez le fichier `app/digital_twin/main.py` :
```python
# Changez le fichier JSON ici :
sim = Simulator(scenario_file="app/digital_twin/scenarios/scenario_soleil.json")
```
Puis reconstruisez :
```bash
docker-compose up -d --build sensor-simulator
```

## Topics MQTT

| Topic | Sens | Description |
| :--- | :--- | :--- |
| `home/sys/clock` | Sim -> Backend | Heure virtuelle (ISO format) |
| `home/sensors/living_room/metrics` | Sim -> InfluxDB | Température, Conso, Solaire... |
| `home/+/valve/set` | Backend -> Sim | Ordre d'ouverture vanne (0-100%) |
