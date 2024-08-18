#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import json
import mimetypes
import os
import re
from typing import Any, Dict, List, Tuple

import unidiff
from dotenv import load_dotenv
from gitlab import Gitlab
from langchain_core.documents import Document


def get_gitlab_client() -> Tuple[Gitlab, int, int, str]:
    # Load environment variables
    gitlab_url = os.getenv("CI_SERVER_URL", "https://gitlab.com/")
    oauth_token = os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", "")
    project_id = os.getenv("CI_PROJECT_ID", "")
    commit_sha = os.getenv("CI_COMMIT_SHA", "")
    merge_request_iid = os.getenv("CI_MERGE_REQUEST_IID", "")

    # Initialize the GitLab client
    gitlab_client = Gitlab(
        url=gitlab_url,
        # job_token=os.getenv('CI_JOB_TOKEN', ''),
        # private_token=os.getenv('"GITLAB_PROJECT_ACCESS_TOKEN', ''),
        oauth_token=oauth_token,
        api_version=4,
    )

    # Get the current project
    project = gitlab_client.projects.get(project_id)

    # [DEBUG] Get the current commit from merge request
    if commit_sha == "":
        merge_request = project.mergerequests.get(merge_request_iid)
        commit = merge_request.commits().next()
        commit_sha = commit.attributes["id"]
    # Get the current commit
    commit = project.commits.get(commit_sha)

    # If not merge request pipelines,
    # Get the latest merge request iid from commit sha
    if merge_request_iid == "":
        merge_requests = commit.merge_requests(
            state="opened", order_by="updated_at", sort="desc"
        )
        if merge_requests.count == 0:
            exit()
        merge_request_iid = merge_requests[0]["iid"]
    # Get the latest merge request
    merge_request = project.mergerequests.get(merge_request_iid)
    return (gitlab_client, int(project_id), int(merge_request_iid), commit_sha)


def get_documents_merge_request(
    gitlab_client: Gitlab, project_id: int, merge_request_iid: int
) -> List[Document]:
    body = get_body_merge_request(gitlab_client, project_id, merge_request_iid)
    diffs = get_diffs_merge_request(gitlab_client, project_id, merge_request_iid)
    docs = []
    for diff in diffs:
        metadata = body | diff
        metadata.pop("diff_content")
        doc = Document(page_content=diff["diff_content"], metadata=metadata)
        docs.append(doc)
    return docs


def get_documents_commit(
    gitlab_client: Gitlab, project_id: int, merge_request_iid: int, commit_sha: str
) -> List[Document]:
    body = get_body_merge_request(gitlab_client, project_id, merge_request_iid)
    diffs = get_diffs_commit(gitlab_client, project_id, commit_sha)
    docs = []
    for diff in diffs:
        metadata = body | diff
        metadata.pop("diff_content")
        doc = Document(page_content=diff["diff_content"], metadata=metadata)
        docs.append(doc)
    return docs


def get_document_code_summaries(docs: List[Document]) -> Document:
    code_summaries = ""
    for doc in docs:
        if doc.metadata["diff_status"] not in ["add", "modify"]:
            continue
        MR_CODE_SUMMARY = """
        - ファイル: {diff_file}
        {diff_summary}
        """
        code_summaries += MR_CODE_SUMMARY.format(
            diff_file=doc.metadata["file_path"],
            diff_summary=doc.metadata["summary"],
        )

    return Document(
        page_content=code_summaries,
        metadata={
            "title": docs[0].metadata["title"] or "",
            "description": docs[0].metadata["description"] or "",
        },
    )


def get_body_merge_request(
    gitlab_client: Gitlab, project_id: int, merge_request_iid: int
) -> Dict[str, Any]:
    project = gitlab_client.projects.get(project_id)
    merge_request = project.mergerequests.get(merge_request_iid)
    body = merge_request.attributes
    return {
        "title": body["title"],
        "description": body["description"],
        "author": {"name": body["author"]["name"]},
        # "diffs": diffs_list,
    }


def get_diffs_merge_request(
    gitlab_client: Gitlab, project_id: int, merge_request_iid: int
) -> List[Dict[str, Any]]:
    project = gitlab_client.projects.get(project_id)
    merge_request = project.mergerequests.get(merge_request_iid)

    # Get commits of merge request
    commit_list = merge_request.commits()
    latest_commit = commit_list.next()

    # Get the sha of the latest/oldest commit
    latest_commit_sha = latest_commit.attributes["id"]
    for commit in commit_list:
        oldest_commit_sha = commit.attributes["id"]

    # Get diffs from the oldest commit to the latest commit
    diffs = project.repository_compare(oldest_commit_sha, latest_commit_sha)
    return get_diffs(diffs["diffs"])


def get_diffs_commit(
    gitlab_client: Gitlab, project_id: int, commit_sha: str
) -> List[Dict[str, Any]]:
    project = gitlab_client.projects.get(project_id)
    commit = project.commits.get(commit_sha)
    diffs = commit.diff()
    return get_diffs(diffs)


def get_diffs(diffs: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Generate the list of the changed files
    changed_files = []
    for diff in diffs:
        # Set the old/new file path at the head of the diff
        old_path = diff["old_path"]
        new_path = diff["new_path"]
        diff_content = f"""--- a/{old_path}\n+++ b/{new_path}\n{diff["diff"]}"""
        diff_file = io.StringIO(diff_content)

        # Analysis diff file
        patch = unidiff.PatchSet(diff_file)[0]

        # Get diff status
        if patch.is_added_file:
            diff_status = "add"
        elif patch.is_removed_file:
            diff_status = "delete"
        elif patch.is_rename:
            diff_status = "rename"
        elif patch.is_modified_file:
            diff_status = "modify"
        else:
            diff_status = "unknown"

        # Get mime types
        filetype = get_filetype(diff["new_path"])

        # TODO: diff_contentは、一行ごとに配列で持たせたほうがいいかも...?
        changed_file = {
            "file_path": diff["new_path"],
            "diff_status": diff_status,
            "add_count": patch.added,
            "delete_count": patch.removed,
            "diff_content": diff_content,
            "file_type": filetype,
        }
        changed_files.append(changed_file)
    return changed_files


def get_filetype(filepath: str) -> str:
    # TODO: CPythonのmimetypesモジュールにプルリク出してもいいかも
    mimetypes.add_type("text/x-toml", ".toml")
    mimetypes.add_type("text/x-yaml", ".yml")
    mimetypes.add_type("text/x-yaml", ".yaml")
    mimetypes.add_type("text/x-sh", ".gitignore")
    guess_type = mimetypes.guess_type(filepath)[0] or ""
    mime_type = re.sub("^[a-z]+/", "", guess_type)
    mime_type = re.sub("^x-", "", mime_type)
    mime_type = re.sub("^plain", "text", mime_type)
    return mime_type


def comment_merge_request_note(
    gitlab_client: Gitlab, project_id: int, merge_request_iid: int, comment: str
) -> str:
    project = gitlab_client.projects.get(project_id)
    merge_request = project.mergerequests.get(merge_request_iid)
    merge_request_note = merge_request.notes.create({"body": comment})
    return merge_request_note.to_json()


def update_merge_request_body(
    gitlab_client: Gitlab,
    project_id: int,
    merge_request_iid: int,
    title: str,
    description: str,
) -> str:
    project = gitlab_client.projects.get(project_id)
    merge_request = project.mergerequests.get(merge_request_iid)
    # TODO: 以下のコードは動かない
    # merge_request.attributes["title"] = title
    # merge_request.attributes["description"] = description
    # merge_request.save()
    return merge_request.to_json()


if __name__ == "__main__":
    if os.path.isfile(".env"):
        load_dotenv()

    print("\033[32m" + "# " + get_gitlab_client.__name__ + "\033[0m")
    (gitlab_client, project_id, merge_request_iid, commit_sha) = get_gitlab_client()
    print("- project_id: " + str(project_id))
    print("- merge_request_iid: " + str(merge_request_iid))
    print("- commit_sha: " + str(commit_sha))
    print()

    print("\033[32m" + "# " + get_body_merge_request.__name__ + "\033[0m")
    merge_request_dict = get_body_merge_request(
        gitlab_client, project_id, merge_request_iid
    )
    print()

    print("\033[32m" + "# " + get_diffs_merge_request.__name__ + "\033[0m")
    merge_request_diffs = get_diffs_merge_request(
        gitlab_client, project_id, merge_request_iid
    )
    print(json.dumps(merge_request_diffs, indent=2))
    print()

    print("\033[32m" + "# " + get_diffs_commit.__name__ + "\033[0m")
    diffs = get_diffs_commit(gitlab_client, project_id, commit_sha)
    print(json.dumps(diffs, indent=2))

    print("\033[32m" + "# " + update_merge_request_body.__name__ + "\033[0m")
    body = update_merge_request_body(
        gitlab_client, project_id, merge_request_iid, ":sparkles: 開発中", "開発中WIP"
    )
    print(json.dumps(body, indent=2))
