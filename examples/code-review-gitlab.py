#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from dotenv import load_dotenv

from langchain.globals import set_debug
from langchain_core.prompts import PromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.runnables import RunnablePassthrough
from langchain.text_splitter import CharacterTextSplitter

# from gitlab import Gitlab

sys.path.append(".")
from coderev.utils.gitlab_utils import get_gitlab_client
from coderev.document_loaders.gitlab.MergeRequestLoader import MergeRequestLoader
from coderev.retrievers.gitlab.MergeRequestRetriever import MergeRequestRetriever


# DEBUG ON/OFF
# set_debug(True)
set_debug(False)

if os.path.isfile(".env"):
    load_dotenv()

# ユーザ入力
user_input="カレーの作り方"

# Prompt
prompt = PromptTemplate.from_template("""
あなたは、優秀なプログラマーです。
以下のcontextで示すプルリクエストを参考にして、コードレビューしてください。
また、コードレビューは日本語でお願いします。
<context>{context}</context>
""")

# LLM
OLLAMA_URL = 'http://192.168.11.13:30101'
code_llm = ChatOllama(
    model='deepseek-coder-v2:16b',
    base_url=OLLAMA_URL
)
chat_llm = ChatOllama(
    model='llama3.1:8b',
    base_url=OLLAMA_URL
)
llm = Ollama(
    model='llama3.1:8b',
    base_url=OLLAMA_URL
)

# Embedding models
embed = OllamaEmbeddings(
    model='nomic-embed-text:latest',
    base_url=OLLAMA_URL
)

# Document Loader
(gitlab_client, project_id, merge_request_iid, latest_commit_sha) = get_gitlab_client()
docs_loader = MergeRequestLoader(gitlab_client, project_id, merge_request_iid)
docs = docs_loader.load()

# # Text Splitter
text_splitter = CharacterTextSplitter(
    chunk_size=256,
    chunk_overlap=32
)
splitted_docs = text_splitter.split_documents(docs)

# Vector Store
# texts=[
#     "Pythonについての基本情報",
#     "機械学習の最新トレンド",
#     "データサイエンスの応用例"
# ]
# vectorstore = FAISS.from_texts(texts=texts, embedding=embed)
vectorstore = FAISS.from_documents(documents=splitted_docs, embedding=embed)

# Retriever
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
# retriever = MergeRequestRetriever(
#     gitlab_client, project_id, merge_request_iid
# )

# Chain
chain = (
    { "context": retriever, "question": RunnablePassthrough() }
    | prompt
    | llm
)

# chainの実行
answer = chain.invoke(user_input)
print(answer)
