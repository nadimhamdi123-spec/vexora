
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.integrations.github.auth import create_github_app_jwt


GITHUB_API_URL = "https://api.github.com"


def create_installation_access_token() -> dict[str, Any]:
    """
    Create an access token for a GitHub App installation.
    """

    if not settings.GITHUB_INSTALLATION_ID:
        raise ValueError("GITHUB_INSTALLATION_ID is not configured")

    app_jwt = create_github_app_jwt()

    url = (
        f"{GITHUB_API_URL}/app/installations/"
        f"{settings.GITHUB_INSTALLATION_ID}/access_tokens"
    )

    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = httpx.post(
        url,
        headers=headers,
        timeout=15.0,
    )

    response.raise_for_status()

    data = response.json()

    return {
        "token": data["token"],
        "expires_at": datetime.fromisoformat(
            data["expires_at"].replace("Z", "+00:00")
        ),
    }


def get_repository_languages(
    client: httpx.Client,
    full_name: str,
) -> dict[str, int]:
    """
    Retrieve repository languages and byte counts.
    """

    response = client.get(
        f"{GITHUB_API_URL}/repos/{full_name}/languages"
    )

    response.raise_for_status()

    return response.json()


def get_repository_readme(
    client: httpx.Client,
    full_name: str,
) -> str | None:
    """
    Retrieve repository README content.
    """

    response = client.get(
        f"{GITHUB_API_URL}/repos/{full_name}/readme",
        headers={"Accept": "application/vnd.github.raw+json"},
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()

    return response.text


def get_installation_repositories() -> list[dict[str, Any]]:
    """
    Retrieve all repositories accessible to the GitHub App installation,
    including languages and README content.
    """

    installation = create_installation_access_token()
    token = installation["token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    repositories = []

    with httpx.Client(
        headers=headers,
        timeout=15.0,
    ) as client:

        page = 1
        per_page = 100

        while True:
            response = client.get(
                f"{GITHUB_API_URL}/installation/repositories",
                params={
                    "per_page": per_page,
                    "page": page,
                },
            )

            response.raise_for_status()

            data = response.json()
            page_repositories = data.get("repositories", [])

            for repo in page_repositories:

                full_name = repo["full_name"]

                languages = get_repository_languages(
                    client,
                    full_name,
                )

                readme = get_repository_readme(
                    client,
                    full_name,
                )

                primary_language = repo.get("language")

                repositories.append({
                    "id": repo["id"],
                    "name": repo["name"],
                    "full_name": full_name,
                    "owner": repo["owner"]["login"],
                    "html_url": repo["html_url"],
                    "description": repo.get("description"),
                    "default_branch": repo["default_branch"],
                    "private": repo["private"],
                    "primary_language": primary_language,
                    "languages": languages,
                    "readme": readme,
                })

            if len(page_repositories) < per_page:
                break

            page += 1

    return repositories


def get_repository_by_id(repository_id: int) -> dict[str, Any]:
    """
    Retrieve one repository accessible to the GitHub App installation,
    including languages and README content.
    """

    installation = create_installation_access_token()
    token = installation["token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    with httpx.Client(
        headers=headers,
        timeout=15.0,
    ) as client:

        response = client.get(
            f"{GITHUB_API_URL}/repositories/{repository_id}"
        )

        response.raise_for_status()

        repo = response.json()
        full_name = repo["full_name"]

        languages = get_repository_languages(
            client,
            full_name,
        )

        readme = get_repository_readme(
            client,
            full_name,
        )

        return {
            "id": repo["id"],
            "name": repo["name"],
            "full_name": full_name,
            "owner": repo["owner"]["login"],
            "html_url": repo["html_url"],
            "description": repo.get("description"),
            "default_branch": repo["default_branch"],
            "private": repo["private"],
            "primary_language": repo.get("language"),
            "languages": languages,
            "readme": readme,
        }
