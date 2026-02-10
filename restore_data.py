import json
import os
import time
from pymongo import MongoClient
from elasticsearch import Elasticsearch

# --- CONFIGURATION INTELLIGENTE ---
# Si on est dans Docker, on utilise les noms de services. Sinon localhost.
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
ELASTIC_HOST = os.getenv("ELASTIC_HOST", "localhost")

print(f" Connexion à MongoDB sur : {MONGO_HOST}...")
print(f"Connexion à Elastic sur : {ELASTIC_HOST}...")

client = MongoClient(f"mongodb://{MONGO_HOST}:27017/")
db = client["marmiton_db"]
es = Elasticsearch([f"http://{ELASTIC_HOST}:9200"])

# --- CHARGEMENT JSON ---
print("Lecture du fichier marmiton_data.json...")
try:
    with open('marmiton_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"   -> {len(data)} recettes trouvées.")
except FileNotFoundError:
    print(" ERREUR : Le fichier JSON est introuvable !")
    exit()

# --- INSERTION MONGO ---
print("Insertion dans MongoDB...")
db["recipes"].delete_many({})  # On vide pour être propre
if data:
    db["recipes"].insert_many(data)
print("MongoDB OK.")

# --- INSERTION ELASTIC ---
print("Indexation Elasticsearch...")
try:
    if es.indices.exists(index="recipes-idx"):
        es.indices.delete(index="recipes-idx")
    es.indices.create(index="recipes-idx")

    for recipe in data:
        doc = {k: v for k, v in recipe.items() if k != '_id'}
        # On recrée les champs textes pour la recherche
        doc['ingredients_text'] = ", ".join(recipe.get('ingredients', []))
        doc['steps_text'] = " ".join(recipe.get('steps', []))
        
        es.index(index="recipes-idx", id=recipe['product_id'], document=doc)
    print("  Elastic OK.")
except Exception as e:
    print(f" Warning Elastic: {e}")

print("TOUT EST TERMINÉ ! Actualise ta page.")