#!/usr/bin/env python
# -*- coding: utf-8 -*-

import io
import json
import os
from typing import Any

import unidiff
from dotenv import load_dotenv
from gitlab import Gitlab
from gitlab.v4.objects import MergeRequest, Project
from langchain_core.documents import Document


def get_gitlab_client():
    # Initialize the GitLab client
    gitlab_client = Gitlab(
        url=os.getenv("CI_SERVER_URL", "https://gitlab.com/"),
        # job_token=os.getenv('CI_JOB_TOKEN', ''),
        # private_token=os.getenv('"GITLAB_PROJECT_ACCESS_TOKEN', ''),
        oauth_token=os.getenv("GITLAB_PERSONAL_ACCESS_TOKEN", ""),
        api_version=4,
    )

    # Get the current project
    project_id = os.getenv("CI_PROJECT_ID", "")
    project = gitlab_client.projects.get(project_id)

    # Get the latest merge request
    merge_requests = project.mergerequests.list(
        state="opened", order_by="updated_at", sort="desc"
    )
    if merge_requests.count == 0:
        exit()
    merge_request_iid = merge_requests[0].iid
    merge_request = project.mergerequests.get(merge_request_iid)

    # Get the latest commit of the latest merge request
    latest_commit = merge_request.commits().next()
    latest_commit_sha = latest_commit.attributes["id"]

    return (gitlab_client, int(project_id), int(merge_request_iid), latest_commit_sha)


def get_merge_request_dict(
    gitlab_client, project_id, merge_request_iid
) -> dict[str, Any]:
    project: Project = gitlab_client.projects.get(project_id)
    merge_request: MergeRequest = project.mergerequests.get(merge_request_iid)
    merge_request_dict = merge_request.attributes
    diffs_list = get_merge_request_diffs_list(
        gitlab_client, project_id, merge_request_iid
    )
    return {
        "title": merge_request_dict["title"],
        "description": merge_request_dict["description"],
        "author": {"name": merge_request_dict["author"]["name"]},
        "diffs": diffs_list,
    }


def get_commit_diffs_list() -> dict:
    return


def get_merge_request_diffs_list(
    gitlab_client, project_id, merge_request_iid
) -> list[dict[str, Any]]:
    project: Project = gitlab_client.projects.get(project_id)
    merge_request: MergeRequest = project.mergerequests.get(merge_request_iid)
    commit_list = merge_request.commits()
    latest_commit = commit_list.next()
    latest_commit_sha = latest_commit.attributes["id"]
    for commit in commit_list:
        oldest_commit_sha = commit.attributes["id"]
    print(latest_commit_sha)
    print(oldest_commit_sha)
    diffs = project.repository_compare(oldest_commit_sha, latest_commit_sha)

    for diff in diffs["diffs"]:
        print(json.dumps(diff, indent=2))

    diffs = merge_request.diffs.list(get_all=True)
    changed_files = []
    for diff in diffs:
        diff_files = merge_request.diffs.get(diff.id)
        diff_files_dict = diff_files.attributes.get("diffs", [])
        for diff_file_dict in diff_files_dict:
            # Set the old/new file path at the head of the diff
            old_path = diff_file_dict["old_path"]
            new_path = diff_file_dict["new_path"]
            diff_file = io.StringIO(
                f"""--- a/{old_path}\n+++ b/{new_path}\n{diff_file_dict["diff"]}"""
            )
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

            # TODO: diff_contentは、一行ごとに配列で持たせたほうがいいかも...?

            changed_file = {
                "file_path": diff_file_dict["new_path"],
                "diff_status": diff_status,
                "add_count": patch.added,
                "delete_count": patch.removed,
                "diff_content": diff_file_dict["diff"],
            }
            changed_files.append(changed_file)
    return changed_files


def get_merge_request_document() -> list[Document]:
    return


if __name__ == "__main__":
    if os.path.isfile(".env"):
        load_dotenv()

    print("\033[32m" + "# get_gitlab_client" + "\033[0m")
    (gitlab_client, project_id, merge_request_iid, commit_sha) = get_gitlab_client()
    print("- project_id: " + str(project_id))
    print("- merge_request_iid: " + str(merge_request_iid))
    print("- commit_sha: " + str(commit_sha))
    print()

    print("\033[32m" + "# get_merge_request_dict" + "\033[0m")
    merge_request_dict = get_merge_request_dict(
        gitlab_client, project_id, merge_request_iid
    )
    # print(json.dumps(merge_request_dict, indent=2))
    print()

    print("\033[32m" + "# get_merge_request_diffs_list" + "\033[0m")
    # merge_request_diffs = get_merge_request_diffs_list(
    #     gitlab_client, project_id, merge_request_iid
    # )
    # print(json.dumps(merge_request_diffs, indent=2))
    print()
