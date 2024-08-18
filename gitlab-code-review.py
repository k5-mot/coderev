#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from dotenv import load_dotenv
from langchain.globals import set_debug
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from langchain_motex.document_loaders.gitlab_merge_request_loader import (
    GitlabMergeRequestLoader,
)
from langchain_motex.retrievers.gitlab_merge_request_retriever import (
    GitlabMergeRequestRetriever,
)
from langchain_motex.utils.gitlab_utils import get_gitlab_client, get_merge_request_dict

# DEBUG ON/OFF
# set_debug(True)
set_debug(False)

if os.path.isfile(".env"):
    load_dotenv()


# Template
TEMPLATE_CODE_SUMMARY = """あなたは優秀なプログラマーです。
以下に示すコードの差分を元に、簡単に要約してください。
要約は、レビュー担当者がこの変更で何が行われたかをより迅速かつ簡単に理解できるような文章にしてください。

要約は、完全に客観的なものに限定し、意見や提案は含みません。
要約の例は次の通りです。:
```このdiffには関数`create_database`,`delete_database`に変更があり、
これらの関数にパラメータ`force`が追加されています。```

ファイル{name}のコードの差分は、次の通りです。:
```{language}
{content}
```
"""
TEMPLATE_CODE_REVIEW = """あなたは優秀なプログラマーかつコードレビュー担当者です。
以下に示すコードの差分を元に、コードレビューしてください。
また、コードの変更が正しいかどうかを確認して、編集者に対して提案を行ってください。

ファイル{name}のコードの差分は、次の通りです。:
```{language}
{content}
```
"""
TEMPLATE_MR_SUMMARY = """あなたは優秀なプログラマーです。
コードレビュー担当者がプルリクエスト(PR)の内容を素早く把握するために、以下のPRについての情報を提供してください。

提供していただきたい項目は次の通りです。
- このPRの変更内容を記述してください。
- このPRの目的を記述してください。
- このPRを次に示す属性の一つに分類してください。:feature, fix, refactor, perf, test, doc, ci, style, chore

以下はこのPRに関する情報です。:
PRのタイトル: {title}
PRの説明: {description}

以下は変更されたファイルとその変更内容の要約です。:
```text
{code_summaries}
```
"""

# Prompt
prompt_code_summary = PromptTemplate(
    template=TEMPLATE_CODE_SUMMARY, input_variables=["name", "language", "content"]
)
prompt_code_review = PromptTemplate(
    template=TEMPLATE_CODE_REVIEW, input_variables=["name", "language", "content"]
)
prompt_mr_review = PromptTemplate(
    template=TEMPLATE_MR_SUMMARY, input_variables=["metadata", "code_summaries"]
)

# LLM
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
llm_chat = ChatOllama(model="deepseek-coder-v2:16b", base_url=OLLAMA_URL)
llm_code = ChatOllama(model="llama3.1:8b", base_url=OLLAMA_URL)
llm = Ollama(model="llama3.1:8b", base_url=OLLAMA_URL)

# Embedding models
embed = OllamaEmbeddings(model="nomic-embed-text:latest", base_url=OLLAMA_URL)

# Document Loader
(gitlab_client, project_id, merge_request_iid, latest_commit_sha) = get_gitlab_client()
docs_loader = GitlabMergeRequestLoader(gitlab_client, project_id, merge_request_iid)
docs = docs_loader.load()

# # Text Splitter
# text_splitter = CharacterTextSplitter(chunk_size=256, chunk_overlap=32)
# splitted_docs = text_splitter.split_documents(docs)

# Vector Store
# texts=[
#     "Pythonについての基本情報",
#     "機械学習の最新トレンド",
#     "データサイエンスの応用例"
# ]
# vectorstore = FAISS.from_texts(texts=texts, embedding=embed)
# vectorstore = FAISS.from_documents(documents=splitted_docs, embedding=embed)

# Retriever
retriever = GitlabMergeRequestRetriever(gitlab_client, project_id, merge_request_iid)
# retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# Code review chain
for doc in docs:
    # Code summary
    chain_code_summary = (
        {
            "name": RunnableLambda(lambda x: x.metadata["file_path"]),
            "language": RunnableLambda(lambda x: x.metadata["file_type"]),
            "content": RunnableLambda(lambda x: x.page_content),
        }
        | prompt_code_summary
        | llm_code
    )
    doc.metadata["summary"] = chain_code_summary.invoke(doc).content

    # Code review
    chain_code_review = (
        {
            "name": RunnableLambda(lambda x: x.metadata["file_path"]),
            "language": RunnableLambda(lambda x: x.metadata["file_type"]),
            "content": RunnableLambda(lambda x: x.page_content),
        }
        | prompt_code_review
        | llm_code
    )
    doc.metadata["review"] = chain_code_review.invoke(doc).content

    print(doc.metadata["file_path"])
    # print(doc.metadata["summary"])
    # print(doc.metadata["review"])

    if os.path.exists("./logs/outputs_code_review.txt"):
        os.remove("./logs/outputs_code_review.txt")
    with open("./logs/outputs_code_review.txt", mode="a", encoding="utf_8") as f:
        f.write("## " + doc.metadata["file_path"] + "\n")
        f.write(doc.metadata["summary"])
        f.write("\n")

    if os.path.exists("./logs/outputs_code_summary.txt"):
        os.remove("./logs/outputs_code_summary.txt")
    with open("./logs/outputs_code_summary.txt", mode="a", encoding="utf_8") as f:
        f.write("## " + doc.metadata["file_path"] + "\n")
        f.write(doc.metadata["review"])
        f.write("\n")


MR_CODE_SUMMARY = """
- ファイル: {diff_file}
{diff_summary}
"""
code_summaries = ""
for doc in docs:
    if doc.metadata["diff_status"] not in ["add", "modify"]:
        continue
    code_summaries += MR_CODE_SUMMARY.format(
        diff_file=doc.metadata["file_path"],
        diff_summary=doc.metadata["summary"],
    )

mrdoc = Document(
    page_content=code_summaries,
    metadata={
        "title": docs[0].metadata["title"] or "",
        "description": docs[0].metadata["description"] or "",
    },
)
print(mrdoc.page_content)
print(mrdoc.metadata)

# Merge request chain
chain_mr_review = (
    {
        "title": RunnableLambda(lambda x: x.metadata["title"]),
        "description": RunnableLambda(lambda x: x.metadata["description"]),
        "code_summaries": RunnableLambda(lambda x: x.page_content),
    }
    | prompt_mr_review
    | llm_code
)
mrdoc.metadata["summary"] = chain_mr_review.invoke(mrdoc).content
print(mrdoc.metadata["summary"])

if os.path.exists("./logs/outputs_mr_review.txt"):
    os.remove("./logs/outputs_mr_review.txt")
with open("./logs/outputs_mr_review.txt", mode="a", encoding="utf_8") as f:
    f.write(mrdoc.metadata["summary"])

# Chain
# chain = {"context": retriever, "question": RunnablePassthrough()} | prompt | llm

# chainの実行
# answer = chain.invoke(user_input)
# print(answer)
