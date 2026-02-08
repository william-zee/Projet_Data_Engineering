# 🥘 Marmiton Data Intelligence

Plateforme d'analyse de données culinaires (ETL + Dashboard).
Réalisé dans le cadre de l'évaluation Data Engineering.

## 🎯 Conformité aux Spécifications
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

## 🛠 Architecture
1. **Scraper** : Bot Python qui simule un navigateur Chrome. Il génère un `product_id` unique (Hash MD5) pour chaque recette pour éviter les doublons.
2. **MongoDB** : Stocke les données brutes JSON.
3. **Elasticsearch** : Indexe les textes pour permettre la recherche floue (Fuzzy search) dans l'App.
4. **App** : Interface utilisateur connectée aux deux bases de données.

## 🚀 Lancement du projet

1. **Prérequis** : Docker Desktop installé.
2. **Démarrage** :
   ```bash
   docker-compose up --build