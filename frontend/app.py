import streamlit as st
import requests
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")

st.title("Documentation Chat Assistant")

base_url = st.text_input("Enter documentation base URL:")

if st.button("Scrape Documentation"):
    if not base_url:
        st.warning("Please enter a base URL.")
    else:
        try:
            response = requests.post(f"{BACKEND_URL}/scrape", json={"base_url": base_url})
            response.raise_for_status()
            st.success("Documentation scraped successfully!")
        except requests.exceptions.RequestException as e:
             st.error(f"Error scraping documentation: {e}")
    
query = st.text_input("Enter your question:")

if st.button("Ask Question"):
    if not query:
        st.warning("Please enter a question")
    else:
        try:
            response = requests.post(f"{BACKEND_URL}/chat", json={"query": query})
            response.raise_for_status()
            result = response.json()
            st.write("Answer:")
            st.write(result.get("response", "No response"))
        except requests.exceptions.RequestException as e:
            st.error(f"Error: {e}")