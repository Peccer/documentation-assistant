import os
import openai
import logging
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

openai.api_key = os.environ["OPENAI_API_KEY"]
    
def create_vector_store(scraped_data):
    """Creates a vector store from scraped documentation."""
    documents = [Document(page_content=text, metadata={"source": url})
                    for url, text in scraped_data.items()]
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    split_docs = text_splitter.split_documents(documents)
    embeddings = OpenAIEmbeddings()
    vector_store = FAISS.from_documents(split_docs, embeddings)
    return vector_store

def query_vector_store(vector_store, query):
    """Queries the vector store and gets context."""
    if not vector_store:
        return "No documentation found yet. Please provide a valid base url."
    docs = vector_store.similarity_search(query, k=3) #k=3 to get 3 sources
    return docs

def generate_response(query, context_docs):
    """Generates a response using OpenAI with context."""
    if not context_docs:
        return "I can't answer that without context, make sure the documentation base url was provided"
    context_text = "\n\n".join([doc.page_content for doc in context_docs])
    prompt = f"""
        You are a helpful documentation assistant. Your purpose is to provide answers and give advice about the documentation provided.
        Use the following pieces of documentation to answer the question at the end. 
        If the answer is not explicitly within the context, just say \"I don't know based on the provided context\".
        Documentation:
        {context_text}

        Question: {query}
    """
    try:
      response = openai.ChatCompletion.create(
          model="gpt-3.5-turbo",
          messages=[{"role": "user", "content": prompt}]
      )
      return response.choices[0].message.content
    except Exception as e:
       logging.error(f"OpenAI Error: {e}")
       return "I encountered an error. Please try again later."