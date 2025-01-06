# Documentation Chat Assistant

A tool that crawls and scrapes documentation from a given URL and then uses RAG with OpenAI's GPT to create a chat assistant.

## Features
- Automatically scrapes website's API documentation using provided base URL.
- Utilizes RAG and OpenAI GPT for chat-based question answering.
- Frontend is a Streamlit application and backend is a Flask app
- Backend and frontend are hosted in Google Cloud Run.
- Cloud Build pipeline for automated deployment.

## Setup Instructions

### Prerequisites
- A Google Cloud Project.
- Google Cloud SDK installed and configured.
- Docker installed.
- A GitHub repository for your project.
- OpenAI API Key

### Steps

1. **Clone the repository:**
    ```bash
    git clone <your_repository_url>
    cd documentation-assistant
    ```
2. **Set up environment variables:**
   -   Create a `.env` file in each `backend` and `frontend` directories.
   -   Add necessary variables, such as `OPENAI_API_KEY`, `GCS_BUCKET_NAME` (in backend/.env) and `BACKEND_URL`(only in frontend/.env)
3. **Deploy cloud build**

   -  Create a cloud build trigger
   -  Connect it to your main branch
   -  Commit the changes

##  Notes

-   The application uses `gpt-3.5-turbo` model by default. You can change it in the `rag.py` file.
-   Cloud build will deploy the frontend and the backend to google cloud run, the `BACKEND_URL` should be replaced with your backend url in the `cloudbuild.yaml` file.
-   The backend exposes a health check endpoint `/health`, you can use it to check if the service is up and running.
-   The scraping logic in `scraper.py` could be fine tuned based on the website structure.
- The logging level can be set in the docker enviroment variable LOG_LEVEL, the values can be DEBUG, INFO, WARNING, ERROR and CRITICAL