from setuptools import setup, find_packages

setup(
   name='documentation_assistant',
   version='0.1.0',
   packages=find_packages(),
   install_requires=[
       'Flask',
       'requests',
       'beautifulsoup4',
       'openai',
       'langchain',
       'faiss-cpu',
       'python-dotenv',
       'flask-cors',
       'tiktoken',
       'google-cloud-logging',
       'google-cloud-storage',
       'google-cloud-aiplatform'
   ],
)