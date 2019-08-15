#!/usr/bin/env python3
import os
import re
import sys
import semver
import subprocess
import gitlab

def git(*args):
    return subprocess.check_output(["git"] + list(args))

def verify_env_var_presence(name):
    if name not in os.environ:
        raise Exception(f"Expected the following environment variable to be set: {name}")

def extract_gitlab_url_from_project_url():
    project_url = os.environ['CI_PROJECT_URL']
    project_path = os.environ['CI_PROJECT_PATH']

    return project_url.split(f"/{project_path}", 1)[0]

def extract_merge_request_id_from_commit():
    message = git("log", "-1", "--pretty=%B")
    matches = re.search(r'(\S*\/\S*!)(\d)', message.decode("utf-8"), re.M|re.I)
    
    if matches == None:
        raise Exception("Unable to extract merge request from commit message: {message}")

    return matches.group(2)

def retrieve_labels_from_merge_request(merge_request_id):
    project_id = os.environ['CI_PROJECT_ID']
    gitlab_private_token = os.environ['NPA_PASSWORD']

    gl = gitlab.Gitlab(extract_gitlab_url_from_project_url(), private_token=gitlab_private_token)
    gl.auth()

    project = gl.projects.get(project_id)
    merge_request = project.mergerequests.get(merge_request_id)

    return merge_request.labels

def get_bump_tag_from_merge_message():
    message = git("log", "-1", "--pretty=%B")
    matches = re.search(r'(-bump-minor-|-bump-major-)', message.decode("utf-8"), re.M|re.I)
    if matches == None:
        return []
    return matches.group(2)


def bump(latest):
    try:
        # Try to use the merge request labels
        merge_request_id = extract_merge_request_id_from_commit()
        labels = retrieve_labels_from_merge_request(merge_request_id)
    except:
        # Mege request labels didn't work (maybe there wasn't a merge request)
        labels = get_bump_tag_from_merge_message()

    if "bump-minor" in labels or "-bump-minor-" in labels:
        return semver.bump_minor(latest)
    elif "bump-major" in labels or "-bump-major-" in labels:
        return semver.bump_major(latest)
    else:
        return semver.bump_patch(latest)

def tag_repo(tag):
    repository_url = os.environ["CI_REPOSITORY_URL"]
    with open("~/.netrc","w") as f:
        f.write("machine %s\n\tlogin %s\n\tpassword %s\n"%(os.environ["CI_SERVER_HOST"],os.environ["NPA_USERNAME"],os.environ["NPA_PASSWORD"]))

    print(repository_url)
    with open("~/.netrc","r") as f:
        print(f.read())

    git("remote", "set-url", "--push", "origin", repository_url)
    git("tag", tag)
    git("push", "origin", tag)        

def main():
    env_list = ["CI_REPOSITORY_URL", "CI_PROJECT_ID", "CI_PROJECT_URL", "CI_PROJECT_PATH", "NPA_USERNAME", "NPA_PASSWORD", "CI_SERVER_HOST"]
    [verify_env_var_presence(e) for e in env_list]

    try:
        latest = git("describe", "--tags").decode().strip()
    except subprocess.CalledProcessError:
        # Default to version 1.0.0 if no tags are available
        version = "1.0.0"
    else:
        # Skip already tagged commits
        if '-' not in latest:
            print(latest)
            return 0

        version = bump(latest)

    tag_repo(version)
    print(version)

    return 0


if __name__ == "__main__":
    sys.exit(main())
