import streamlit as st
from elasticsearch import Elasticsearch
from pymongo import MongoClient
import os
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="Marmiton Data Project", page_icon="👨‍🍳", layout="wide")

# Connexion aux services Docker (ou localhost si lancé en local)
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
ELASTIC_HOST = os.getenv("ELASTIC_HOST", "localhost")

@st.cache_resource
def init_connection():
    try:
        es = Elasticsearch([f"http://{ELASTIC_HOST}:9200"])
        client = MongoClient(f"mongodb://{MONGO_HOST}:27017/")
        db = client["marmiton_db"]
        return es, db
    except Exception as e:
        return None, None

es, db = init_connection()

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("👨‍🍳 Navigation")
page = st.sidebar.radio("Menu", ["Dashboard & KPIs", "Moteur de Recherche", "Specs & Doc"])

st.sidebar.markdown("---")
st.sidebar.header("Filtres Dynamiques")
selected_cats = st.sidebar.multiselect("Catégories", ["entree", "plat-principal", "dessert"], default=["plat-principal"])

# --- PAGE 1: DASHBOARD ---
if page == "Dashboard & KPIs":
    st.title(" Dashboard Analytique")
    
    if db is not None:
        # Récupération des données Mongo pour les stats
        recipes = list(db["recipes"].find({"category": {"$in": selected_cats}}))
        
        if recipes:
            df = pd.DataFrame(recipes)
            
            # KPI Cards
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Recettes Totales", len(df))
            col2.metric("Note Moyenne", f"{df['rating'].mean():.2f}/5")
            
            # Calcul difficulté la plus fréquente
            top_diff = df['difficulty'].mode()[0] if 'difficulty' in df.columns else "N/A"
            col3.metric("Difficulté Top", top_diff)
            
            # Temps moyen
            avg_time = df['duration_min'].mean() if 'duration_min' in df.columns else 0
            col4.metric("Temps Moyen", f"{int(avg_time)} min")

            st.markdown("### 🥧 Répartition par Difficulté")
            if 'difficulty' in df.columns:
                st.bar_chart(df['difficulty'].value_counts())
            
            st.markdown("### ⭐ Distribution des Notes")
            if 'rating' in df.columns:
                st.line_chart(df['rating'].value_counts())
                
            st.markdown("### 📋 Aperçu des Données Brutes")
            st.dataframe(df[["name", "category", "rating", "difficulty"]].head(10))
        else:
            st.info("Aucune donnée trouvée dans MongoDB pour les catégories sélectionnées.")
    else:
        st.error("Impossible de se connecter à MongoDB.")


elif page == "Moteur de Recherche":
    st.title("🔍 Recherche Intelligente")
    
    # 1. Choix du mode dans la sidebar (spécifique à cette page)
    search_mode = st.sidebar.radio("Mode de recherche", ["Classique", "Frigo (aliments) "])
    
    search_body = None
    
    # --- MODE 1 : RECHERCHE CLASSIQUE ---
    if search_mode == "Classique":
        query = st.text_input("Ingrédient ou plat (ex: chocolat, tarte)...", "chocolat")
        
        if query:
            search_body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["name", "ingredients_text", "steps_text"],
                        "fuzziness": "AUTO"
                    }
                },
                "size": 500
            }


    # --- MODE 2 : FRIGO VIDE ---
    elif search_mode == "Frigo (aliments) ":
        st.info("Indiquez ce qu'il vous reste, on trouve la recette !")
        ingredients_input = st.text_input("Vos ingrédients (séparés par une virgule)", "oeufs, farine, lait")
        
        if ingredients_input:
            # 1. Nettoyage : minuscules et suppression des espaces
            ing_list = [x.strip().lower() for x in ingredients_input.split(",")]
            
            should_clauses = []
            for ing in ing_list:
                if not ing: continue # ignorer les chaines vides
                
                # On crée une sous-requête "OU" pour chaque ingrédient
                # Soit ça match exactement (avec tolérance faute), soit ça match avec des jokers (*mot*)
                should_clauses.append({
                    "bool": {
                        "should": [
                            # Option A: Recherche classique tolérante (gère "oeuf" vs "oeufs")
                            {
                                "match": {
                                    "ingredients_text": {
                                        "query": ing,
                                        "fuzziness": "AUTO",
                                        "operator": "and"
                                    }
                                }
                            },
                            # Option B: Recherche Joker (Sauve le cas "1oeuf" collé)
                            {
                                "wildcard": {
                                    "ingredients_text": {
                                        "value": f"*{ing}*", # Trouve "oeuf" dans "1oeuf"
                                        "case_insensitive": True
                                    }
                                }
                            }
                        ]
                    }
                })
            
            # 2. Construction de la requête principale
            search_body = {
                "query": {
                    "bool": {
                        # "must" ici signifie que la recette DOIT matcher au moins une des conditions
                        # Mais pour être flexible on utilise often 'should' avec minimum_should_match
                        "should": should_clauses,
                        # On demande qu'au moins 50% des ingrédients demandés soient présents
                        # Tu peux monter à "100%" si tu es strict
                        "minimum_should_match": "1" 
                    }
                },
                "size": 500
            }

    # --- EXÉCUTION COMMUNE (Elasticsearch) ---
    if es and search_body:
        try:
            resp = es.search(index="recipes-idx", body=search_body)
            hits = resp['hits']['hits']
            
            st.success(f"{len(hits)} résultats trouvés.")
            
            for hit in hits:
                source = hit['_source']
                score = hit['_score']
                duration = source.get('duration_min', 0)
                
                # --- AFFICHAGE DE LA CARTE RECETTE (Même affichage pour les 2 modes) ---
                with st.expander(f"{source.get('name')} ({source.get('category')}) - Pertinence: {score:.2f}"):
                    
                    c1, c2 = st.columns([1, 3])
                    
                    with c1:
                        # Gestion de l'image
                        img_url = source.get('image_url')
                        if img_url and img_url.startswith("http"):
                            st.image(img_url, use_container_width=True)
                        else:
                            st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/1024px-No_image_available.svg.png", width=150)
                        
                        st.metric("Difficulté", source.get('difficulty', 'N/A'))
                        st.metric("Note", f"{source.get('rating', 0)}/5")
                        st.metric("Temps", f"{duration} min")

                    with c2:
                        st.markdown("#### 🥕 Ingrédients")
                        ingredients = source.get('ingredients', [])
                        if ingredients:
                            for ing in ingredients:
                                st.markdown(f"- {ing}")
                        else:
                            st.info("Ingrédients non disponibles")

                        st.markdown("---")
                        
                        st.markdown("#### 🍳 Préparation")
                        steps = source.get('steps', [])
                        if steps:
                            for i, step in enumerate(steps):
                                st.markdown(f"**{i+1}.** {step}")
                        
                        st.markdown(f"[Voir la recette originale sur Marmiton]({source.get('url')})")

        except Exception as e:
            st.error(f"Erreur Elastic: {e}")
# --- PAGE 3: SPECS & DOC ---
elif page == "Specs & Doc":
    st.title(" Documentation Technique")
    
    st.markdown("""
    ### Modèle de Données
    Voici comment sont structurées nos données après le scraping Selenium.
    """)
    
    # Affichage plus joli qu'un bloc de code brut
    st.info("Données validées et stockées en JSON BSON (Mongo) et Index inversé (Elastic).")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Champs Principaux")
        st.markdown("""
        * **product_id** : Identifiant unique (Hash MD5 de l'URL)
        * **name** : Titre de la recette
        * **category** : Entrée / Plat / Dessert
        * **rating** : Note sur 5 (Float)
        * **difficulty** : Facile / Moyen / Difficile
        """)
    
    with col2:
        st.markdown("#### Champs Riches (Selenium)")
        st.markdown("""
        * **ingredients** : Liste complète (`Array[String]`)
        * **steps** : Étapes de préparation (`Array[String]`)
        * **image_url** : Lien vers l'image HD
        * **url** : Lien source
        """)

    st.markdown("---")
    st.markdown("### 🏗️ Architecture")
    st.success("Architecture Docker Microservices validée.")
    st.graphviz_chart("""
    digraph {
        rankdir=LR;
        Scraper_Selenium -> MongoDB [label="Stockage Brut"];
        Scraper_Selenium -> Elasticsearch [label="Indexation Texte"];
        MongoDB -> Streamlit_App [label="Dashboard"];
        Elasticsearch -> Streamlit_App [label="Recherche"];
    }
    """)