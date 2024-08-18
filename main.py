#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil

from dotenv import load_dotenv
from langchain.globals import set_debug
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda

from langchain_motex.document_loaders.gitlab_commit_loader import GitlabCommitLoader
from langchain_motex.document_loaders.gitlab_merge_request_loader import (
    GitlabMergeRequestLoader,
)
from langchain_motex.utils.gitlab_utils import (
    comment_merge_request_note,
    get_document_code_summaries,
    get_gitlab_client,
)

# Initialize
set_debug(False)
if os.path.isfile(".env"):
    load_dotenv()
if os.getenv("CI_PIPELINE_SOURCE") == "merge_request_event":
    FLAG_MERGE_REQUEST = True
else:
    FLAG_MERGE_REQUEST = False

# ----------------------------
# Template
# ----------------------------
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

# ----------------------------
# Prompt
# ----------------------------
prompt_code_summary = PromptTemplate(
    template=TEMPLATE_CODE_SUMMARY, input_variables=["name", "language", "content"]
)
prompt_code_review = PromptTemplate(
    template=TEMPLATE_CODE_REVIEW, input_variables=["name", "language", "content"]
)
prompt_mr_review = PromptTemplate(
    template=TEMPLATE_MR_SUMMARY, input_variables=["metadata", "code_summaries"]
)

# ----------------------------
# LLM
# ----------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
llm_chat = ChatOllama(model="deepseek-coder-v2:16b", base_url=OLLAMA_URL)
llm_code = ChatOllama(model="llama3.1:8b", base_url=OLLAMA_URL)
llm = Ollama(model="llama3.1:8b", base_url=OLLAMA_URL)

# ----------------------------
# Embedding models
# ----------------------------
embed = OllamaEmbeddings(model="nomic-embed-text:latest", base_url=OLLAMA_URL)

# ----------------------------
# Document Loader
# ----------------------------
(gitlab_client, project_id, merge_request_iid, commit_sha) = get_gitlab_client()
if FLAG_MERGE_REQUEST:
    docs_loader = GitlabMergeRequestLoader(gitlab_client, project_id, merge_request_iid)
else:
    docs_loader = GitlabCommitLoader(
        gitlab_client, project_id, merge_request_iid, commit_sha
    )
docs = docs_loader.load()

# ----------------------------
# Code Summary & Review Chain
# ----------------------------
for doc in docs:
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
    print("Finished: " + doc.metadata["file_path"])

# ----------------------------
# Transformers
# - Summaries Aggregation
# ----------------------------
# TODO: 各コードの要約を結合する処理は、LangChainコンポーネントを継承する形で実現したい
doc_summarized = get_document_code_summaries(docs)

# ----------------------------
# Merge Request Summary chain
# ----------------------------
chain_mr_review = (
    {
        "title": RunnableLambda(lambda x: x.metadata["title"]),
        "description": RunnableLambda(lambda x: x.metadata["description"]),
        "code_summaries": RunnableLambda(lambda x: x.page_content),
    }
    | prompt_mr_review
    | llm_code
)
doc_summarized.metadata["summary"] = chain_mr_review.invoke(doc_summarized).content
print(doc_summarized.metadata["summary"])

# ----------------------------
# Feedback to GitLab
# ----------------------------
if FLAG_MERGE_REQUEST:
    # TODO: ここに以下の処理を追加する予定
    # 1. MR要約とコードごとの要約をdescriptionに追記
    # 2. MRの分類をtitleの先頭に追記
    pass
else:
    # TODO: ここに以下の処理を追加する予定
    # 1. コミットされるたびに、コードの要約とレビューをコメント
    # 2. MRのdescriptionに新しい要約を反映
    comment = (
        "## コード要約\n\n" + doc_summarized.page_content + "\n\n## コードレビュー\n\n"
    )
    for doc in docs:
        comment += "- " + doc.metadata["file_path"] + "\n"
        comment += doc.metadata["review"] + "\n\n"
    comment_merge_request_note(gitlab_client, project_id, merge_request_iid, comment)


# ----------------------------
# Logging
# ----------------------------
# Clear previous logs
if os.path.isdir("./logs"):
    shutil.rmtree("./logs")
os.makedirs("./logs", exist_ok=True)

# Log outputs
for doc in docs:
    with open("./logs/outputs_code_review.txt", mode="a", encoding="utf_8") as f:
        f.write("## " + doc.metadata["file_path"] + "\n")
        f.write(doc.metadata["summary"])
        f.write("\n")
    with open("./logs/outputs_code_summary.txt", mode="a", encoding="utf_8") as f:
        f.write("## " + doc.metadata["file_path"] + "\n")
        f.write(doc.metadata["review"])
        f.write("\n")
with open("./logs/outputs_mr_review.txt", mode="a", encoding="utf_8") as f:
    f.write(doc_summarized.metadata["summary"])
