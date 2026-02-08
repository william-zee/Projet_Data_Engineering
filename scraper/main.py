import time
import os
import logging
import random
import hashlib
import re 
import json 
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from pymongo import MongoClient, UpdateOne
from elasticsearch import Elasticsearch

# --- CONFIG LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ScraperBot")

class MarmitonScraper:
    def __init__(self):
        self.mongo_host = os.getenv("MONGO_HOST", "localhost")
        self.elastic_host = os.getenv("ELASTIC_HOST", "localhost")
        self.db = None
        self.es = None

        chrome_options = Options()
        chrome_options.add_argument("--headless=new") 
        chrome_options.add_argument("--disable-search-engine-choice-screen")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
        
        chrome_options.page_load_strategy = 'eager' 
        
        logger.info("🚗 Initialisation du driver Chrome...")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)
        self.wait = WebDriverWait(self.driver, 10)

        self.categories = ["entree", "plat-principal", "dessert"]
        
        
        self.pages_per_cat = 33 

    def connect(self):
        for i in range(30):
            try:
                if self.db is None: 
                    self.db = MongoClient(f"mongodb://{self.mongo_host}:27017/")["marmiton_db"]
                
                if self.es is None:
                    self.es = Elasticsearch([f"http://{self.elastic_host}:9200"])
                
                if not self.es.ping(): 
                    raise Exception("Elasticsearch not ready")
                
                logger.info(" Connexion BDD & Elastic OK")
                return True
            except Exception as e:
                logger.warning(f"⏳ Attente services ({i+1}/30)... {e}")
                time.sleep(2)
        return False

    def scrape(self):
        all_recipes = []
        cookies_accepted = False

        # Init site
        try:
            self.driver.get("https://www.marmiton.org")
            if not cookies_accepted:
                try:
                    btn = self.wait.until(EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button")))
                    btn.click()
                    cookies_accepted = True
                    time.sleep(1)
                except: pass
        except Exception as e:
            logger.error(f"Erreur init site: {e}")

        for cat in self.categories:
            logger.info(f"Traitement de la catégorie : {cat.upper()} ...")
            
            urls_to_visit = []
            seen = set()

            # --- PAGINATION ---
            for page_num in range(1, self.pages_per_cat + 1):
                try:
                    url_search = f"https://www.marmiton.org/recettes/recherche.aspx?aqt={cat}&page={page_num}"
                    logger.info(f" Chargement de la page {page_num}...")
                    
                    try:
                        self.driver.get(url_search)
                    except TimeoutException:
                        logger.warning(" Timeout liste. On continue.")
                    
                    time.sleep(1.5)
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(0.5)

                    soup = BeautifulSoup(self.driver.page_source, "html.parser")
                    links = soup.find_all("a", href=True)
                    
                    count_before = len(urls_to_visit)
                    
                    for l in links:
                        href = l['href']
                        if "/recettes/recette_" in href:
                            full = "https://www.marmiton.org" + href if href.startswith("/") else href
                            if full not in seen:
                                urls_to_visit.append(full)
                                seen.add(full)
                    
                    logger.info(f"     -> {len(urls_to_visit) - count_before} nouveaux liens trouvés.")

                except Exception as e:
                    logger.error(f" Erreur page {page_num}: {e}")
                    continue
            
            logger.info(f"   🎯 TOTAL liens à visiter pour {cat}: {len(urls_to_visit)}")

            # --- VISITE RECETTES ---
            for url in urls_to_visit:
                try:
                    logger.info(f"   -> Visite : {url}")
                    try:
                        self.driver.get(url)
                    except TimeoutException:
                        logger.warning("Timeout page. Analyse partielle.")
                    
                    time.sleep(1) 
                    page_soup = BeautifulSoup(self.driver.page_source, "html.parser")
                    
                    # 1. ID & TITRE
                    p_id = hashlib.md5(url.encode()).hexdigest()
                    h1 = page_soup.find("h1")
                    title = h1.get_text(strip=True) if h1 else "Recette Inconnue"
                    if title == "Recette Inconnue": continue

                    # 2. INGREDIENTS 
                    ingredients = [d.get_text(" ", strip=True) for d in page_soup.select(".item__ingredient .ingredient-name")]
                    if not ingredients: ingredients = [d.get_text(" ", strip=True) for d in page_soup.select(".card-ingredient-title")]
                    
                    steps = [s.get_text(strip=True) for s in page_soup.select(".recipe-step-list__container p")]

                    # 3. IMAGE
                    img_url = ""
                    meta_img = page_soup.find("meta", property="og:image")
                    if meta_img: img_url = meta_img.get("content", "")

                    mots_interdits = ["placeholder", "logo", "default", "no-photo", "p_global_en_tete"]
                    est_mauvaise_image = False
                    if not img_url: est_mauvaise_image = True
                    else:
                        for mot in mots_interdits:
                            if mot in img_url.lower():
                                est_mauvaise_image = True
                                break
                    if est_mauvaise_image:
                        img_url = "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?q=80&w=800&auto=format&fit=crop"

                    # 4. INFOS & DIFFICULTÉ
                    difficulty = "Moyen"
                    infos_items = [i.get_text(strip=True).lower() for i in page_soup.select(".recipe-primary__item")]
                    
                    for info in infos_items:
                        if "très facile" in info:
                            difficulty = "Très facile"
                            break
                        elif "facile" in info:
                            difficulty = "Facile"
                            break
                        elif "difficile" in info:
                            difficulty = "Difficile"
                            break
                        elif "moyen" in info:
                            difficulty = "Moyen"
                            break

                    
                    duration = 0
                    header_text = " ".join(infos_items).lower().replace("heure", "h")
                    
                    if not any(char.isdigit() for char in header_text):
                        header_text = page_soup.get_text(" ", strip=True).lower()[:1000].replace("heure", "h")

                    try:
                        p_hour = re.search(r'(\d+)\s*h', header_text)
                        if p_hour: duration += int(p_hour.group(1)) * 60
                        
                        p_min = re.search(r'(\d+)\s*min', header_text) 
                        if p_min:
                            duration += int(p_min.group(1))
                        elif not p_hour: 
                            p_min_short = re.search(r'temps\s*[:\s]\s*(\d+)\s*m', header_text)
                            if p_min_short: duration += int(p_min_short.group(1))
                    except Exception:
                        duration = 0
                    
                    if duration == 0:
                        logger.warning(f"TEMPS NON TROUVÉ (0 min) pour : {url}")

                    # 6. REVIEWS & NOTE
                    reviews_count = 0
                    try:
                        rev_tag = page_soup.select_one(".recipe-header__rating-count")
                        if rev_tag:
                            nums = re.findall(r'\d+', rev_tag.get_text())
                            if nums: reviews_count = int(nums[0])
                    except: pass

                    rating = 0.0
                    match_rate = page_soup.select_one(".recipe-header__rating-text")
                    if match_rate:
                        try: rating = float(match_rate.get_text().strip().replace("/5", "").replace(",", "."))
                        except: pass

                    recipe = {
                        "product_id": p_id,
                        "name": title,
                        "category": cat,
                        "url": url,
                        "image_url": img_url,
                        "difficulty": difficulty,
                        "rating": rating,
                        "reviews_count": reviews_count,
                        "duration_min": duration,      
                        "ingredients": ingredients,
                        "steps": steps,
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    all_recipes.append(recipe)
                    logger.info(f"     + {title[:20]}... ({rating} | {duration}m)")

                except Exception as e:
                    logger.error(f"Erreur: {e}")
                    continue

        return all_recipes

    def save(self, data):
        if not data:
            logger.warning("⚠️ Aucune donnée.")
            return

        logger.info(f"💾 Traitement de {len(data)} recettes...")

        # --- 1. SAUVEGARDE JSON (SÉCURITÉ) ---
        try:
            with open("marmiton_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(" Fichier JSON créé !")
        except Exception as e:
            logger.error(f"Erreur JSON: {e}")

        # --- 2. MONGODB ---
        try:
            ops = [UpdateOne({'product_id': d['product_id']}, {'$set': d}, upsert=True) for d in data]
            self.db["recipes"].bulk_write(ops)
            logger.info(" MongoDB OK")
        except Exception as e:
            logger.error(f"Erreur Mongo: {e}")

        # --- 3. ELASTICSEARCH ---
        try:
            if not self.es.indices.exists(index="recipes-idx"):
                self.es.indices.create(index="recipes-idx")
            for d in data:
                clean_doc = {k:v for k,v in d.items() if k != '_id'}
                clean_doc['ingredients_text'] = ", ".join(d['ingredients'])
                clean_doc['steps_text'] = " ".join(d['steps'])
                self.es.index(index="recipes-idx", id=d['product_id'], document=clean_doc)
            logger.info("   -> 🔎 Elasticsearch OK")
        except Exception as e:
            logger.error(f"Erreur Elastic: {e}")

    def close(self):
        if self.driver:
            self.driver.quit()
            logger.info("Driver Chrome fermé.")


if __name__ == "__main__":
    bot = MarmitonScraper()
    
    # 1. On se connecte
    if bot.connect():
        
        # --- ETAPE 1 : ON NETTOIE D'ABORD (MÉNAGE) ---
        print("🧹 NETTOYAGE EN COURS (AVANT SCRAPING)...")
        
        # A. On vide MongoDB
        bot.db["recipes"].drop()
        print("MongoDB vidé.")
        
        # B. On vide Elasticsearch
        try:
            if bot.es.indices.exists(index="recipes-idx"):
                bot.es.indices.delete(index="recipes-idx")
                print("Elasticsearch vidé.")
        except Exception as e:
            print(f"Info Elastic: {e}")
            
        print(" Bases de données prêtes à recevoir les nouvelles données !")
       

        # --- ETAPE 2 : ON LANCE LE SCRAPING ---
        logger.info(" Démarrage du Scraper HYBRIDE (Gros Volume)...")
        try:
            data = bot.scrape()     # On récupère les données
            bot.save(data)          # On sauvegarde les données
        except KeyboardInterrupt:
            logger.warning("Arrêt manuel.")
        finally:
            bot.close()
            logger.info(" Terminé. Les données sont sauvegardées et sécurisées.")