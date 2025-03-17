import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import json

# IMPORTS from your existing code
from scraper import scrape_documentation
from utils import (
    setup_logging,
    save_scraped_data_to_gcs,
    load_scraped_data_from_gcs,
    create_rag_corpus,
    import_files_to_corpus,
    generate_rag_response,
    load_corpus_registry,
    save_corpus_registry,
    handle_new_documentation,
    extract_text_from_file,
    cleanup_gcs_bucket_parallel,
    GCS_BUCKET_NAME
)
from conversation_store import (
    create_conversation,
    get_conversation,
    list_conversations,
    delete_conversation,
    add_message_to_conversation,
)
from vertexai.preview import rag

load_dotenv()

app = Flask(__name__)
CORS(app)
setup_logging()

DATA_FILE_NAME = "scraped_data.json"
PROJECT_ID = os.environ.get("PROJECT_ID", "your-project-id")
LOCATION = os.environ.get("LOCATION", "us-central1")

logging.info(f"GCS_BUCKET_NAME: {GCS_BUCKET_NAME}")

scraped_data = {}
# If you want to load previously scraped data from GCS
if GCS_BUCKET_NAME:
    scraped_data = load_scraped_data_from_gcs(GCS_BUCKET_NAME, DATA_FILE_NAME)
    if scraped_data:
        logging.info("Scraped data is available")

# Load corpus registry from local JSON
load_corpus_registry()


#####################################
# Endpoint: /scrape (Creates NEW corpus)
#####################################
@app.route("/scrape", methods=["POST"])
def scrape():
    """
    Scrape a base_url and create a NEW RAG corpus with the given display_name & description.
    """
    data = request.get_json()
    base_url = data.get("base_url")
    max_pages = data.get("max_pages", 100)
    display_name = data.get("display_name")
    description = data.get("description")

    if not base_url or not display_name or not description:
        return jsonify({"error": "base_url, display_name and description are required"}), 400

    logging.info(f"Starting scraping of {base_url}")
    global scraped_data

    # Perform scraping
    scraped_data = scrape_documentation(base_url, max_pages=max_pages)
    if not scraped_data:
        return jsonify({"error": "Could not scrape the provided base url"}), 400

    # Optionally save the scraped data
    if GCS_BUCKET_NAME:
        save_scraped_data_to_gcs(scraped_data, GCS_BUCKET_NAME, DATA_FILE_NAME)

    # Create new corpus and import data
    response = handle_new_documentation(base_url, display_name, description, scraped_data)

    if response["status"] == "OK":
        logging.info("Documents imported to RAG Corpus")
        save_corpus_registry()
        return jsonify({
            "message": "Scraping completed, data indexed with Vertex AI RAG.",
            "corpus_name": response["corpus_name"]
        }), 200
    else:
        return jsonify({"error": "Could not index the documentation."}), 400


###################################
# NEW Endpoint: /rag_corpora/<corpus_name>/scrape
# Scrape a base_url and ADD to EXISTING corpus
###################################
@app.route("/rag_corpora/<path:corpus_name>/scrape", methods=["POST"])
def scrape_to_existing_corpus(corpus_name):
    """
    Scrapes a website and imports that data into an EXISTING corpus.
    JSON body:
      { "base_url": "...", "max_pages": 100 }

    1. Scrape up to max_pages from base_url
    2. Convert each page to .txt
    3. Upload those .txt files to GCS
    4. import_files_to_corpus(corpus_name=...)
    5. Cleanup
    """
    data = request.get_json()
    base_url = data.get("base_url")
    max_pages = data.get("max_pages", 100)

    if not base_url:
        return jsonify({"error": "base_url is required"}), 400

    # Check if the corpus actually exists
    try:
        existing_corpus = rag.get_corpus(corpus_name)
        if not existing_corpus:
            return jsonify({"error": f"Corpus {corpus_name} not found."}), 404
    except Exception as e:
        return jsonify({"error": f"Error retrieving corpus: {e}"}), 404

    # 1. Scrape
    logging.info(f"Scraping {base_url} for existing corpus {corpus_name} ...")
    new_data = scrape_documentation(base_url, max_pages)
    if not new_data:
        return jsonify({"error": "No data scraped from that base URL."}), 400

    # 2. Convert and upload to GCS
    import tempfile, os
    paths = []
    gcs_paths = []
    from utils import upload_to_gcs

    try:
        # Each key in new_data is a URL, each value is the text
        for url, text in new_data.items():
            if not isinstance(text, str) or not text.strip():
                continue
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp_file:
                tmp_file.write(text)
                tmp_file_path = tmp_file.name
                paths.append(tmp_file_path)

            gcs_path = f"gs://{GCS_BUCKET_NAME}/{os.path.basename(tmp_file_path)}"
            upload_to_gcs(GCS_BUCKET_NAME, os.path.basename(tmp_file_path), text, content_type="text/plain")
            gcs_paths.append(gcs_path)

        if not gcs_paths:
            return jsonify({"error": "Scraped pages produced no valid text."}), 400

        # 3. import_files_to_corpus
        batch_size = 25
        for i in range(0, len(gcs_paths), batch_size):
            batch = gcs_paths[i : i+batch_size]
            import_files_to_corpus(corpus_name=corpus_name, paths=batch)

    finally:
        # 4. cleanup
        for p in paths:
            os.remove(p)
        cleanup_gcs_bucket_parallel(GCS_BUCKET_NAME)

    return jsonify({
        "message": f"Successfully scraped {len(new_data)} pages and imported into corpus {corpus_name}."
    }), 200


#####################################
# Legacy Single Query Chat (No conversation)
#####################################
@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json()
    query = body.get("query")
    mode = body.get("mode", "auto")
    selected_corpora = body.get("selected_corpora", [])

    if not query:
        return jsonify({"error": "Query is required"}), 400

    rag_response = generate_rag_response(
        query=query,
        mode=mode,
        manual_corpora=selected_corpora
    )
    if rag_response["status"] == "OK":
        return jsonify({"response": rag_response["response"]})
    else:
        return jsonify({"response": rag_response["response"]}), 400


#########################
# Conversation-based Chat
#########################
@app.route("/conversations", methods=["GET"])
def get_conversations():
    convs = list_conversations()
    return jsonify(convs), 200

@app.route("/conversations", methods=["POST"])
def new_conversation():
    data = request.get_json()
    title = data.get("title", "Untitled Conversation")
    conversation_id = create_conversation(title)
    return jsonify({"conversation_id": conversation_id}), 201

@app.route("/conversations/<conversation_id>", methods=["GET"])
def get_single_conversation(conversation_id):
    conv = get_conversation(conversation_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify(conv), 200

@app.route("/conversations/<conversation_id>", methods=["DELETE"])
def delete_single_conversation(conversation_id):
    success = delete_conversation(conversation_id)
    if not success:
        return jsonify({"error": "Conversation not found"}), 404
    return jsonify({"message": "Conversation deleted"}), 200

@app.route("/conversations/<conversation_id>/chat", methods=["POST"])
def conversation_chat(conversation_id):
    data = request.get_json()
    user_message = data.get("message")
    mode = data.get("mode", "auto")
    selected_corpora = data.get("selected_corpora", [])

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    conv = add_message_to_conversation(conversation_id, "user", user_message)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404

    # Build entire chat context
    all_messages = conv["messages"]
    conversation_context = ""
    for m in all_messages:
        if m["role"] == "user":
            conversation_context += f"\nUser: {m['content']}"
        else:
            conversation_context += f"\nAssistant: {m['content']}"

    final_query = (
        f"Conversation so far:\n{conversation_context}\n"
        f"New user query: {user_message}\n"
        "Please respond as a helpful documentation assistant, using relevant docs if available."
    )

    rag_response = generate_rag_response(
        query=final_query,
        mode=mode,
        manual_corpora=selected_corpora
    )
    if rag_response["status"] == "OK":
        assistant_reply = rag_response["response"]
    else:
        assistant_reply = "I encountered an error. Please try again later."

    conv = add_message_to_conversation(conversation_id, "assistant", assistant_reply)
    return jsonify(conv), 200


#################################
# RAG Corpus Management
#################################
@app.route("/rag_corpora", methods=["GET"])
def list_rag_corpora():
    try:
        corpora = rag.list_corpora()
        result = []
        for c in corpora:
            result.append({
                "display_name": c.display_name,
                "name": c.name
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/rag_corpora/<path:corpus_name>", methods=["DELETE"])
def delete_rag_corpus(corpus_name):
    try:
        rag.delete_corpus(corpus_name)
        return jsonify({"message": f"RAG corpus {corpus_name} deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


############################################
# FILE UPLOAD for NEW CORPUS
############################################
@app.route("/upload", methods=["POST"])
def upload():
    """
    Create a NEW corpus from uploaded documents.
    form-data => display_name, description, files[]
    """
    display_name = request.form.get("display_name")
    description = request.form.get("description")
    if not display_name or not description:
        return jsonify({"error": "display_name and description are required"}), 400

    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        return jsonify({"error": "No files uploaded"}), 400

    file_texts = {}
    for f in uploaded_files:
        file_content = f.read()
        parsed_text = extract_text_from_file(file_content, f.filename)
        if parsed_text.strip():
            file_texts[f.filename] = parsed_text

    if not file_texts:
        return jsonify({"error": "No valid text in any file"}), 400

    response = handle_new_documentation("", display_name, description, file_texts)
    if response["status"] == "OK":
        save_corpus_registry()
        return jsonify({
            "message": "File(s) indexed successfully in Vertex RAG",
            "corpus_name": response["corpus_name"]
        }), 200
    else:
        return jsonify({"error": "Could not index the uploaded files."}), 400


############################################
# ADD FILES TO EXISTING CORPUS
############################################
@app.route("/rag_corpora/<path:corpus_name>/add_data", methods=["POST"])
def add_data_to_existing_corpus(corpus_name):
    uploaded_files = request.files.getlist("files")
    if not uploaded_files:
        return jsonify({"error": "No files uploaded"}), 400

    # Check that the corpus actually exists
    try:
        existing_corpus = rag.get_corpus(corpus_name)
        if not existing_corpus:
            return jsonify({"error": "No such corpus."}), 404
    except Exception as e:
        return jsonify({"error": f"Error retrieving corpus: {e}"}), 404

    file_texts = {}
    for f in uploaded_files:
        file_content = f.read()
        parsed_text = extract_text_from_file(file_content, f.filename)
        if parsed_text.strip():
            file_texts[f.filename] = parsed_text

    if not file_texts:
        return jsonify({"error": "No valid text extracted from any file."}), 400

    import tempfile, os
    from utils import upload_to_gcs

    paths = []
    gcs_paths = []
    try:
        for filename, text in file_texts.items():
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp_file:
                tmp_file.write(text)
                tmp_file_path = tmp_file.name
                paths.append(tmp_file_path)

            gcs_path = f"gs://{GCS_BUCKET_NAME}/{os.path.basename(tmp_file_path)}"
            upload_to_gcs(GCS_BUCKET_NAME, os.path.basename(tmp_file_path), text, content_type="text/plain")
            gcs_paths.append(gcs_path)

        if not gcs_paths:
            return jsonify({"error": "No valid documents to import"}), 400

        batch_size = 25
        for i in range(0, len(gcs_paths), batch_size):
            batch = gcs_paths[i : i + batch_size]
            import_files_to_corpus(corpus_name=corpus_name, paths=batch)
    finally:
        for path in paths:
            os.remove(path)
        cleanup_gcs_bucket_parallel(GCS_BUCKET_NAME)

    return jsonify({"message": f"Successfully added {len(gcs_paths)} file(s) to {corpus_name}"}), 200


@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
