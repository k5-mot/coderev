#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from gitlab import Gitlab
from langchain_core.retrievers import BaseRetriever, Document

from langchain_motex.utils.gitlab_utils import get_gitlab_client, get_merge_request_dict


class GitlabMergeRequestRetriever(BaseRetriever):
    gitlab_client: Gitlab
    project_id: int | str
    merge_request_iid: int | str
    merge_request_dict: Dict[str, Any] = {}
    docs: List[Document] = []
    k: int = 5

    def __init__(
        self, gitlab_client: Gitlab, project_id: int | str, merge_request_iid: int | str
    ):
        """Initializes the MergeRequestRetriever."""
        super().__init__(
            gitlab_client=gitlab_client,
            project_id=project_id,
            merge_request_iid=merge_request_iid,
        )
        self.merge_request_dict = get_merge_request_dict(
            gitlab_client, project_id, merge_request_iid
        )
        self.docs.append(Document(page_content=json.dumps(self.merge_request_dict)))

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Return the first k documents from the list of documents"""
        return self.docs[: self.k]

    async def _aget_relevant_documents(self, query: str) -> List[Document]:
        """(Optional) async native implementation."""
        return self.docs[: self.k]


if __name__ == "__main__":
    if os.path.isfile(".env"):
        load_dotenv()

    (gitlab_client, project_id, merge_request_iid, commit_sha) = get_gitlab_client()
    retriever = GitlabMergeRequestRetriever(
        gitlab_client, project_id, merge_request_iid
    )
    docs = retriever.invoke("fix bug")

    for doc in docs:
        mr = json.loads(doc.page_content)
        print("Title: ", mr["title"])
        print("Description: ", mr["description"])
        print("Author: ", mr["author"]["name"])
        print("Diffs: ", len(mr["diffs"]))
        if False:
            for diff in mr["diffs"]:
                print(
                    "  "
                    + diff["file_path"]
                    + " ("
                    + diff["diff_status"]
                    + "): "
                    + "Add("
                    + str(diff["add_count"])
                    + ") / "
                    + "Del("
                    + str(diff["delete_count"])
                    + ")"
                )
