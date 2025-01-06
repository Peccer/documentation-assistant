import os
import logging
from google.cloud import storage
import json
import pickle
import faiss
from io import BytesIO

def setup_logging():
     log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
     numeric_level = getattr(logging, log_level, None)
     if not isinstance(numeric_level, int):
         raise ValueError(f"Invalid log level: {log_level}")
     logging.basicConfig(level=numeric_level, format='%(asctime)s - %(levelname)s - %(message)s')
 
def upload_to_gcs(bucket_name, filename, content, content_type="application/octet-stream"):
    """Uploads content to GCS."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(content, content_type=content_type)
    logging.info(f"Uploaded {filename} to GCS bucket {bucket_name}")

def download_from_gcs(bucket_name, filename):
    """Downloads content from GCS."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    if blob.exists():
        content = blob.download_as_string()
        logging.info(f"Downloaded {filename} from GCS bucket {bucket_name}")
        return content
    else:
        logging.info(f"{filename} not found in GCS bucket {bucket_name}")
        return None
 
def load_vector_store_from_gcs(bucket_name, index_filename, embeddings):
     """Loads a vector store from GCS."""
     try:
         index_bytes = download_from_gcs(bucket_name, index_filename)
         if not index_bytes:
             return None
         
         index = faiss.read_index(BytesIO(index_bytes))
         vector_store = FAISS(embedding_function=embeddings, index=index)
         logging.info(f"Successfully loaded vector store from GCS")
         return vector_store
     except Exception as e:
         logging.error(f"Error loading vector store from GCS: {e}")
         return None


def save_vector_store_to_gcs(vector_store, bucket_name, index_filename):
     """Saves the vector store to GCS."""
     try:
         with BytesIO() as bio:
           faiss.write_index(vector_store.index, faiss.cast_integer_to_float_ptr(bio))
           upload_to_gcs(bucket_name, index_filename, bio.getvalue())
         logging.info("Successfully saved vector store to GCS")
     except Exception as e:
         logging.error(f"Error saving vector store to GCS: {e}")
 

def save_scraped_data_to_gcs(scraped_data, bucket_name, filename):
  """Saves the scraped data to GCS."""
  try:
      content = json.dumps(scraped_data)
      upload_to_gcs(bucket_name, filename, content, content_type="application/json")
      logging.info("Successfully saved scraped data to GCS")
  except Exception as e:
      logging.error(f"Error saving scraped data to GCS: {e}")

def load_scraped_data_from_gcs(bucket_name, filename):
  """Loads scraped data from GCS."""
  try:
      content = download_from_gcs(bucket_name, filename)
      if content:
          return json.loads(content)
      else:
          return None
  except Exception as e:
      logging.error(f"Error loading scraped data from GCS: {e}")
      return None