import streamlit as st
import requests
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")

st.set_page_config(page_title="Doc Chat Assistant", layout="wide")

##############################
# SIDEBAR: Conversations
##############################
st.sidebar.title("Chat Sessions")

# Get all existing conversations
try:
    resp = requests.get(f"{BACKEND_URL}/conversations")
    resp.raise_for_status()
    conversation_list = resp.json()
except:
    conversation_list = []

conversation_titles = ["[New Conversation]"] + [
    f"{c.get('title','Untitled')} ({c['id'][:8]})"
    for c in conversation_list
]
selected_conversation_title = st.sidebar.selectbox(
    "Select a conversation",
    conversation_titles
)

if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = None

def reload_conversations():
    st.rerun()

if selected_conversation_title == "[New Conversation]":
    st.session_state["conversation_id"] = None
else:
    start_idx = selected_conversation_title.find("(")
    end_idx = selected_conversation_title.find(")")
    if start_idx != -1 and end_idx != -1:
        chosen_id = selected_conversation_title[start_idx+1:end_idx]
        for c in conversation_list:
            if c["id"].startswith(chosen_id):
                st.session_state["conversation_id"] = c["id"]
                break

if st.sidebar.button("Delete Current Conversation"):
    if st.session_state["conversation_id"]:
        requests.delete(f"{BACKEND_URL}/conversations/{st.session_state['conversation_id']}")
        st.session_state["conversation_id"] = None
        st.rerun()

##############################
# Manage RAG Corpora in sidebar:
##############################
st.sidebar.subheader("Manage RAG Corpora")

# 1. Get current corpora
try:
    corpora_resp = requests.get(f"{BACKEND_URL}/rag_corpora")
    corpora_resp.raise_for_status()
    all_corpora = corpora_resp.json()  # list of {display_name, name}
except Exception as e:
    all_corpora = []
    st.sidebar.error(f"Could not load corpora: {e}")

if all_corpora:
    # Let user delete a corpus
    corpus_options = [f"{c['display_name']} | {c['name']}" for c in all_corpora]
    selected_corpus_str = st.sidebar.selectbox("Select a corpus to delete:", corpus_options)
    
    if st.sidebar.button("Delete Selected Corpus"):
        corpus_full_name = selected_corpus_str.split("|", 1)[1].strip()
        try:
            del_resp = requests.delete(f"{BACKEND_URL}/rag_corpora/{corpus_full_name}")
            if del_resp.status_code == 200:
                st.sidebar.success("Corpus deleted successfully.")
            else:
                st.sidebar.error(f"Error deleting corpus: {del_resp.text}")
        except Exception as ex:
            st.sidebar.error(f"Request failed: {ex}")
else:
    st.sidebar.write("No RAG corpora found.")


##############################
# MAIN PAGE
##############################
st.title("Documentation Chat Assistant")


############################################
# Section 1: Scrape Documentation
############################################
with st.expander("Scrape Documentation"):
    st.write("Scrape docs from a website and index them in Vertex RAG.")

    corpus_mode_scrape = st.radio(
        "Corpus Mode",
        ["Create New", "Add to Existing"],
        horizontal=True
    )

    if corpus_mode_scrape == "Create New":
        base_url = st.text_input("Enter documentation base URL:")
        display_name = st.text_input("Enter a display name for the new corpus:")
        description = st.text_area("Enter a description for the new corpus:")
        max_pages = st.number_input("Max pages to scrape", min_value=1, value=50, step=1)

        if st.button("Scrape to NEW Corpus"):
            if not base_url or not display_name or not description:
                st.warning("Please fill in base_url, display_name, description.")
            else:
                payload = {
                    "base_url": base_url,
                    "max_pages": max_pages,
                    "display_name": display_name,
                    "description": description
                }
                try:
                    resp = requests.post(f"{BACKEND_URL}/scrape", json=payload)
                    if resp.status_code == 200:
                        st.success("Scraping completed! Data indexed in new corpus.")
                    else:
                        st.error(f"Error: {resp.text}")
                except Exception as e:
                    st.error(f"Request failed: {e}")

    else:  # "Add to Existing"
        if not all_corpora:
            st.info("No existing corpora. Please create one first.")
        else:
            base_url_existing = st.text_input("Enter documentation base URL:")
            max_pages_existing = st.number_input("Max pages to scrape", min_value=1, value=50, step=1)
            # Choose from existing corpora
            corpus_display_names = [c["display_name"] for c in all_corpora]
            selected_corpus = st.selectbox("Choose existing corpus", corpus_display_names)

            if st.button("Scrape & Add to EXISTING Corpus"):
                if not base_url_existing or not selected_corpus:
                    st.warning("Please enter base_url and select a corpus.")
                else:
                    # Find the full resource name
                    corpus_full_name = None
                    for c in all_corpora:
                        if c["display_name"] == selected_corpus:
                            corpus_full_name = c["name"]
                            break
                    if not corpus_full_name:
                        st.error("Selected corpus not found in registry.")
                    else:
                        payload = {"base_url": base_url_existing, "max_pages": max_pages_existing}
                        endpoint = f"{BACKEND_URL}/rag_corpora/{corpus_full_name}/scrape"
                        try:
                            resp = requests.post(endpoint, json=payload)
                            if resp.status_code == 200:
                                st.success(f"Scraped and imported into {selected_corpus}!")
                            else:
                                st.error(f"Error: {resp.text}")
                        except Exception as ex:
                            st.error(f"Request failed: {ex}")


############################################
# Section 2: Upload Documents
############################################
with st.expander("Upload Documents (PDF, DOCX, Excel, etc.)"):
    st.write("Upload local files to be indexed in RAG.")

    corpus_mode_upload = st.radio(
        "Corpus Mode for Upload",
        ["Create New", "Add to Existing"],
        horizontal=True
    )

    uploaded_files = st.file_uploader(
        "Select files to upload",
        type=["pdf", "docx", "doc", "xlsx", "xls", "txt"],
        accept_multiple_files=True
    )

    if corpus_mode_upload == "Create New":
        display_name_upload = st.text_input("Display name for new corpus:")
        description_upload = st.text_area("Description for new corpus:")

        if st.button("Upload to NEW Corpus"):
            if not display_name_upload or not description_upload:
                st.warning("Please enter display name & description.")
            elif not uploaded_files:
                st.warning("Please select at least one file.")
            else:
                files_data = []
                for f in uploaded_files:
                    files_data.append(("files", (f.name, f.read(), f"type")))

                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/upload",
                        data={
                            "display_name": display_name_upload,
                            "description": description_upload
                        },
                        files=files_data
                    )
                    if resp.status_code == 200:
                        st.success("File(s) uploaded and indexed in new corpus!")
                    else:
                        st.error(f"Error: {resp.text}")
                except Exception as e:
                    st.error(f"Request failed: {e}")

    else:
        if not all_corpora:
            st.info("No existing corpora. Please create one first.")
        else:
            corpus_display_names = [c["display_name"] for c in all_corpora]
            selected_corpus_upload = st.selectbox("Choose existing corpus:", corpus_display_names)

            if st.button("Upload Files to EXISTING Corpus"):
                if not selected_corpus_upload or not uploaded_files:
                    st.warning("Please select a corpus and file(s).")
                else:
                    corpus_full_name = None
                    for c in all_corpora:
                        if c["display_name"] == selected_corpus_upload:
                            corpus_full_name = c["name"]
                            break
                    if not corpus_full_name:
                        st.error("Selected corpus not found.")
                    else:
                        files_data = []
                        for f in uploaded_files:
                            files_data.append(("files", (f.name, f.read(), f"type")))

                        endpoint = f"{BACKEND_URL}/rag_corpora/{corpus_full_name}/add_data"
                        try:
                            add_resp = requests.post(endpoint, files=files_data)
                            if add_resp.status_code == 200:
                                st.success("Files added successfully to existing corpus!")
                            else:
                                st.error(f"Error: {add_resp.text}")
                        except Exception as e:
                            st.error(f"Request failed: {e}")


############################################
# Section 3: Chat Interface
############################################
st.subheader("Chat Interface")

if not st.session_state["conversation_id"]:
    st.info("No conversation selected. Create a new one below:")
    new_title = st.text_input("New conversation title", "")
    if st.button("Start New Conversation"):
        payload = {"title": new_title if new_title else "Untitled Conversation"}
        try:
            resp = requests.post(f"{BACKEND_URL}/conversations", json=payload)
            resp.raise_for_status()
            new_id = resp.json()["conversation_id"]
            st.session_state["conversation_id"] = new_id
            st.success(f"New conversation created: {new_id[:8]}")
            st.rerun()
        except Exception as e:
            st.error(f"Error creating conversation: {e}")
else:
    conversation_id = st.session_state["conversation_id"]
    st.write(f"**Conversation ID**: {conversation_id}")

    try:
        resp = requests.get(f"{BACKEND_URL}/conversations/{conversation_id}")
        resp.raise_for_status()
        conversation_data = resp.json()
    except:
        st.warning("Could not load conversation. It may have been deleted.")
        st.session_state["conversation_id"] = None
        st.rerun()

    if "messages" in conversation_data:
        for msg in conversation_data["messages"]:
            if msg["role"] == "user":
                st.markdown(f"**You:** {msg['content']}")
            else:
                st.markdown(f"**Assistant:** {msg['content']}")

    st.divider()

    # Let user pick auto/manual corpora selection
    mode = st.radio("Corpora Selection Mode:", ["auto", "manual"], index=0)
    selected_corpora_manual = []
    if mode == "manual":
        if all_corpora:
            all_corpus_display_names = [c["display_name"] for c in all_corpora]
            selected_corpora_manual = st.multiselect(
                "Select which corpus/corpora to use:",
                all_corpus_display_names
            )
        else:
            st.info("No corpora available.")

    user_input = st.text_input("Your message:")
    if st.button("Send"):
        if not user_input.strip():
            st.warning("Enter a message first.")
        else:
            body = {
                "message": user_input,
                "mode": mode,
                "selected_corpora": selected_corpora_manual
            }
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/conversations/{conversation_id}/chat",
                    json=body
                )
                resp.raise_for_status()
                st.rerun()
            except requests.exceptions.RequestException as e:
                st.error(f"Error sending message: {e}")
