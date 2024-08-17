#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import requests
import pprint
import io
import unidiff
from dotenv import load_dotenv
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Union
# from pydantic import BaseModel, Field

from gitlab import Gitlab
from gitlab.v4.objects import Project, ProjectCommit, ProjectIssue, ProjectMergeRequest

from langchain_core.documents import Document
from langchain_core.document_loaders import BaseLoader
from langchain_community.document_loaders import JSONLoader

sys.path.append(".")
from coderev.utils.gitlab_utils import get_gitlab_client, get_merge_request_dict


class MergeRequestLoader(BaseLoader):
    gitlab_client: Gitlab
    project_id: int | str
    merge_request_iid: int | str

    def __init__(self, gitlab_client: Gitlab, project_id: int, merge_request_iid: int):
        """Initializes the GitlabMRLoader."""
        # super().__init__()
        self.gitlab_client=gitlab_client
        self.project_id=project_id
        self.merge_request_iid=merge_request_iid
        # self.merge_request_dict = get_merge_request_dict(gitlab_client, project_id, merge_request_iid)
        # self.doc = Document(page_content=json.dumps(self.merge_request_dict))

    def lazy_load(self) -> Iterator[Document]:
        """Load and return documents from the JSON file."""
        # print(json.dumps(self.merge_request.attributes, indent=2))
        merge_request_dict = get_merge_request_dict(
            self.gitlab_client,
            self.project_id,
            self.merge_request_iid
        )
        doc = Document(page_content=json.dumps(merge_request_dict))
        yield doc


if __name__ == "__main__":
    if os.path.isfile(".env"):
        load_dotenv()

    (gitlab_client, project_id, merge_request_iid, commit_sha) = get_gitlab_client()
    docs_loader = MergeRequestLoader(gitlab_client, project_id, merge_request_iid)
    docs = docs_loader.load()

    for doc in docs:
        mr = json.loads(doc.page_content)
        print("Title: ", mr['title'])
        print("Description: ", mr['description'])
        print("Author: ", mr["author"]["name"])
        print("Diffs: ", len(mr["diffs"]))
        if False:
            for diff in mr["diffs"]:
                print(
                    "  "
                    + diff["file_path"]
                    + " (" + diff["diff_status"] + "): "
                    + "Add(" + str(diff["add_count"]) + ") / "
                    + "Del(" + str(diff["delete_count"]) + ")"
                )
