# 🥘 Marmiton Data Intelligence

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Latest-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Elasticsearch](https://img.shields.io/badge/Elasticsearch-7.17-005571?logo=elasticsearch&logoColor=white)](https://www.elastic.co/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)

> Pipeline ETL complet pour l'extraction, l'indexation et la visualisation de recettes culinaires depuis Marmiton.

---
Plateforme d'analyse de données culinaires (ETL + Dashboard).
Réalisé dans le cadre de l'évaluation Data Engineering.

## Conformité aux Spécifications
Ce projet remplit l'ensemble des critères et bonus demandés :

| Consigne | Implémentation |
|----------|----------------|
| **Scraping** | Script Python `scraper/` avec Selenium (Extraction multi-catégories) |
| **Stockage BDD** | MongoDB (Container `marmiton_mongo`) |
| **Web App** | Streamlit avec graphiques Seaborn & Matplotlib |
| **Docker** | Architecture complète Microservices (4 containers) |
| **Bonus 1** | Scraping temps réel lancé automatiquement au démarrage |
| **Bonus 2** | Utilisation de `docker-compose` |
| **Bonus 3** | Moteur de recherche via **Elasticsearch** |
| **Bonus 4** | Gestion des erreurs et "Mock Data" si le site est inaccessible |

## Architecture
1. **Scraper** : Bot Python qui simule un navigateur Chrome. Il génère un `product_id` unique (Hash MD5) pour chaque recette pour éviter les doublons.
2. **MongoDB** : Stocke les données brutes JSON.
3. **Elasticsearch** : Indexe les textes pour permettre la recherche floue (Fuzzy search) dans l'App.
4. **App** : Interface utilisateur connectée aux deux bases de données.

## Lancement du projet

1. **Prérequis** : Docker Desktop installé.
1.5 
```bash
pip install -r app/requirements.txt
pip install -r scrapper/requirements.txt
```
2. **Démarrage** :
```bash
docker-compose up --build
```
---

##  Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Scraper   │────▶│   MongoDB   │────▶│  Streamlit  │
│  (Selenium) │     │   (BSON)    │     │    App      │
└──────┬──────┘     └─────────────┘     └──────▲──────┘
       │                                       │
       │            ┌─────────────┐            │
       └───────────▶│Elasticsearch│────────────┘
                    │  (Search)   │
                    └─────────────┘
```
---

## Stack Technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Scraper | Selenium + BeautifulSoup | Extraction données dynamiques |
| Storage | MongoDB | Base documentaire NoSQL |
| Search | Elasticsearch 7.17 | Recherche full-text + fuzzy |
| Frontend | Streamlit | Dashboard interactif |
| Infra | Docker Compose | Orchestration 4 containers |

---

##  Quick Start

```bash
# 1. Cloner le repo
git clone https://github.com/username/marmiton-data-intelligence.git
cd marmiton-data-intelligence

# 2. Lancer l'application (scraping complet ~30min)
docker-compose up --build

# 3. Accéder au dashboard
open http://localhost:8501
```

### Démarrage rapide (avec données pré-chargées)

```bash
# Démarrer les services sans scraping
docker-compose up -d mongodb elasticsearch webapp

# Restaurer les données de backup
python restore_data.py
```

---

## Usage

### Dashboard & KPIs
Visualisation des métriques clés : nombre de recettes, note moyenne, difficulté dominante, temps de préparation moyen.

### Moteur de Recherche

| Mode | Description |
|------|-------------|
| **Classique** | Recherche par mot-clé avec tolérance aux fautes |
| **Frigo** | Trouve des recettes selon les ingrédients disponibles |

---

## API & Fonctionnalités

### Accès direct aux bases de données

Le projet expose MongoDB et Elasticsearch directement, permettant des requêtes personnalisées.

---

### Champs indexés dans Elasticsearch

| Champ | Type | Recherchable | Description |
|-------|------|--------------|-------------|
| `name` | text | ✅ Fuzzy | Nom de la recette |
| `ingredients_text` | text | ✅ Fuzzy + Wildcard | Ingrédients concaténés |
| `steps_text` | text | ✅ Fuzzy | Étapes concaténées |
| `category` | keyword | ✅ Exact | Catégorie |
| `difficulty` | keyword | ✅ Exact | Niveau de difficulté |
| `rating` | float | ✅ Range | Note /5 |
| `duration_min` | integer | ✅ Range | Temps en minutes |

---

## Modèle de Données

```json
{
  "product_id": "8f9c019db9d23e88526772d5144a6b7a",
  "name": "Tarte au chocolat",
  "category": "dessert",
  "url": "https://www.marmiton.org/recettes/...",
  "image_url": "https://assets.afcdn.com/...",
  "difficulty": "Facile",
  "rating": 4.8,
  "reviews_count": 127,
  "duration_min": 45,
  "ingredients": ["200g chocolat", "3 oeufs", "..."],
  "steps": ["Préchauffer le four...", "..."],
  "updated_at": "2026-02-07 22:03:40"
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `product_id` | string | Hash MD5 de l'URL (clé unique) |
| `category` | string | `entree` \| `plat-principal` \| `dessert` |
| `difficulty` | string | `Très facile` \| `Facile` \| `Moyen` \| `Difficile` |
| `ingredients` | array | Liste des ingrédients |
| `steps` | array | Étapes de préparation |

---

## Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `MONGO_HOST` | `localhost` | Hôte MongoDB |
| `ELASTIC_HOST` | `localhost` | Hôte Elasticsearch |

### Ports exposés

| Service | Port | URL |
|---------|------|-----|
| Streamlit | `8501` | http://localhost:8501 |
| MongoDB | `27017` | mongodb://localhost:27017 |
| Elasticsearch | `9200` | http://localhost:9200 |

---

## Dépannage

### Elasticsearch out of memory

```yaml
# docker-compose.yml
environment:
  - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
```

### Restauration des données après crash

```bash
python restore_data.py
```

### Le scraper ne démarre pas

Vérifier qu'Elasticsearch est healthy :
```bash
curl http://localhost:9200/_cluster/health
```

### Images manquantes sur les recettes

Les images invalides sont remplacées automatiquement par un placeholder Unsplash.

---

## 📁 Structure du Projet

```
.
├── app/
│   ├── main.py              # Dashboard Streamlit
│   ├── requirements.txt
│   └── Dockerfile
├── scraper/
│   ├── main.py              # Bot Selenium
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml       # Orchestration
├── restore_data.py          # Script de restauration
├── marmiton_data.json       # Backup des données
└── README.md
```

---

## 📄 License

Project maintained by: [longeacc] (https://github.com/longeacc) [william-zee] (https://github.com/william-zee) License: MIT (for original code) | CC-BY-4.0 (for INERIS data) Copyright :

I declare on my honour that the code provided has been produced by me/us, with the exception of the lines below; for each line (or group of lines) borrowed, give the source reference and an explanation of the syntax used any line not declared above is deemed to have been produced by the author(s) of the project. The absence or omission of a declaration will be considered plagiarism.

## Acknowledgments

- [Marmiton](https://www.marmiton.org) — Source des données
- [Streamlit](https://streamlit.io) — Framework dashboard
- [Elastic](https://elastic.co) — Moteur de recherche
