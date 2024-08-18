#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from typing import Iterator

from dotenv import load_dotenv
from gitlab import Gitlab
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from langchain_motex.utils.gitlab_utils import get_documents_commit, get_gitlab_client


class GitlabCommitLoader(BaseLoader):
    gitlab_client: Gitlab
    project_id: int
    merge_request_iid: int

    def __init__(
        self,
        gitlab_client: Gitlab,
        project_id: int,
        merge_request_iid: int,
        commit_sha: str,
    ):
        self.gitlab_client = gitlab_client
        self.project_id = project_id
        self.merge_request_iid = merge_request_iid
        self.commit_sha = commit_sha

    def lazy_load(self) -> Iterator[Document]:
        """Load and return documents from the JSON file."""
        docs = get_documents_commit(
            self.gitlab_client, self.project_id, self.merge_request_iid, self.commit_sha
        )
        for doc in docs:
            yield doc


if __name__ == "__main__":
    if os.path.isfile(".env"):
        load_dotenv()

    (gitlab_client, project_id, merge_request_iid, commit_sha) = get_gitlab_client()
    docs_loader = GitlabCommitLoader(
        gitlab_client, project_id, merge_request_iid, commit_sha
    )
    docs = docs_loader.load()

    for doc in docs:
        print("Title: ", doc.metadata["title"])
        print("Description: ", doc.metadata["description"])
        print("Author: ", doc.metadata["author"]["name"])
        print("Filepath: ", doc.metadata["file_path"])
        print("Status: ", doc.metadata["diff_status"])
        print("Add_lines: ", doc.metadata["add_count"])
        print("Delete_lines: ", doc.metadata["delete_count"])
        print("\n")
        if False:
            print("Diffs: ", doc.page_content)
