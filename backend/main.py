import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from scraper import scrape_documentation
from rag import create_vector_store, query_vector_store, generate_response,  OpenAIEmbeddings
from utils import setup_logging, save_scraped_data_to_gcs, load_scraped_data_from_gcs, save_vector_store_to_gcs, load_vector_store_from_gcs
import pickle

app = Flask(__name__)
CORS(app)

setup_logging()

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
DATA_FILE_NAME = "scraped_data.json"
INDEX_FILE_NAME = "vector_store.index"

vector_store = None
scraped_data = {}

# Load persisted data at startup
if GCS_BUCKET_NAME:
    scraped_data = load_scraped_data_from_gcs(GCS_BUCKET_NAME, DATA_FILE_NAME)
    embeddings = OpenAIEmbeddings()
    if scraped_data:
       vector_store = load_vector_store_from_gcs(GCS_BUCKET_NAME, INDEX_FILE_NAME, embeddings)

@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.get_json()
    base_url = data.get("base_url")

    if not base_url:
        return jsonify({"error": "Base URL is required."}), 400

    logging.info(f"Starting scraping of {base_url}")
    global scraped_data
    global vector_store
    
    scraped_data = scrape_documentation(base_url)
    if not scraped_data:
       return jsonify({"error": "Could not scrape the provided base url"}), 400
    
    vector_store = create_vector_store(scraped_data)

    if GCS_BUCKET_NAME:
        save_scraped_data_to_gcs(scraped_data, GCS_BUCKET_NAME, DATA_FILE_NAME)
        save_vector_store_to_gcs(vector_store, GCS_BUCKET_NAME, INDEX_FILE_NAME)
        logging.info(f"Scraped data and vector store saved to GCS")
    
    logging.info(f"Scraped {len(scraped_data)} pages and created vector store")
    return jsonify({"message": "Scraping completed, vector database initialized."})

@app.route("/chat", methods=["POST"])
def chat():
    query = request.get_json().get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400
    logging.info(f"Received query: {query}")
    docs = query_vector_store(vector_store, query)
    response = generate_response(query, docs)
    logging.info(f"Response generated")
    return jsonify({"response": response})

@app.route("/health", methods=["GET"])
def health():
     return "OK", 200
     
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))