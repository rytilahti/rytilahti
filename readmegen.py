# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "aiohttp==3.13.3",
#   "gql[aiohttp]==4.0.0",
#   "pypistats==1.13.0",
# ]
# ///

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import time
from typing import Any

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
import pypistats

DEBUG = int(os.environ.get("DEBUG", 0))
TOKEN = os.environ["TOKEN"]

SUMMARIZE_AFTER_COUNT = 5
DATE_FORMAT = "%d %B, %Y"

PYPI_PACKAGES = [
    "python-miio",
    "python-kasa",
    "pyHS100",
    "python-eq3bt",
    "python-yeelightbt",
    "python-songpal",
    "python-mirobo",
]


async def fetch_data(query: str) -> dict[str, Any]:
    transport = AIOHTTPTransport(
        url="https://api.github.com/graphql",
        headers={"Authorization": f"bearer {TOKEN}"},
    )
    async with Client(
        transport=transport,
        fetch_schema_from_transport=True,
    ) as session:
        result = await session.execute(gql(query))
        return result


def pretty_project(project: dict[str, Any]) -> str:
    return (
        f'[{project["nameWithOwner"]} \N{EN DASH} {project["description"]}]'
        f'({project["url"]}) '
        f'({project["stargazerCount"]:,} \N{WHITE MEDIUM STAR}, '
        f'{project["forkCount"]:,} \N{FORK AND KNIFE})'
    )


def get_contributions_list(
    contributions: list[dict[str, Any]],
    count: int = SUMMARIZE_AFTER_COUNT,
    contribution_type: str = "contributions",
) -> str:
    output = ""
    logging.info("Found %s contributions of type '%s'", len(contributions), contribution_type)
    for idx, contribution in enumerate(contributions):
        project = contribution["repository"]
        if idx == count:
            output += "\n<details><summary>Show more</summary><p>\n\n"
        output += f'* {contribution["contributions"]["totalCount"]} {contribution_type} to {pretty_project(project)}\n'
    if idx > count:
        output += "</p></details>"
    return output


def get_repos(userdata: dict[str, Any], count: int = SUMMARIZE_AFTER_COUNT) -> str:
    output = ""
    logging.info("Found %s repositories", len(userdata["repositories"]["nodes"]))
    ignored_repos = ["rytilahti/rytilahti", "rytilahti/.github"]
    projects = [p for p in userdata["repositories"]["nodes"] if p["nameWithOwner"] not in ignored_repos]
    if not projects:
        logging.error("No valid projects found after filtering: %s", userdata["repositories"]["nodes"])
    for idx, project in enumerate(projects):
        if idx == count:
            output += "\n<details><summary>Show more</summary><p>\n\n"
        output += f"{idx + 1}. {pretty_project(project)}\n"
    output += "</p></details>"
    return output


def get_counts(userdata: dict[str, Any]) -> defaultdict[str, int]:
    keys = ["stargazerCount", "forkCount"]
    res: defaultdict[str, int] = defaultdict(int)
    for repo in userdata["repositories"]["nodes"]:
        for k in keys:
            res[k] += repo[k]
    return res


def pretty_count(user: dict[str, Any], var: str) -> str:
    return f'{user[var]["totalCount"]:,}'


def fetch_pypistats(func: Any, *args: Any, retries: int = 3, backoff: float = 5.0, **kwargs: Any) -> Any:
    """Call a pypistats function with exponential backoff retries on failure.

    Retries on any exception (e.g. HTTP 429, network timeouts, service outages).
    """
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < retries - 1:
                wait = backoff * (2 ** attempt)
                print(f"Warning: pypistats call failed ({str(e)}), retrying in {wait:.0f}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait)
            else:
                raise


async def main() -> None:
    # monthly stats here just for reference, last_week is also available.
    pypi_recent: dict[str, int] = {}
    for _package in PYPI_PACKAGES:
        try:
            pypi_recent[_package] = json.loads(fetch_pypistats(pypistats.recent, _package, format="json"))["data"]["last_month"]
        except Exception as e:
            print(f"Warning: could not fetch pypistats for {_package} after retries: {e}")
            pypi_recent[_package] = 0
    pypi_recent_count = sum(pypi_recent.values())

    with open("github_query.graphql") as f:
        _q = f.read()
    data = await fetch_data(_q)
    userdata = data["user"]

    contrs = userdata["contributionsCollection"]
    repos = get_repos(userdata)
    counts = get_counts(userdata)
    pull_request_stats = get_contributions_list(
        contrs["pullRequestContributionsByRepository"], contribution_type="pull requests"
    )
    code_review_stats = get_contributions_list(
        contrs["pullRequestReviewContributionsByRepository"], contribution_type="reviews"
    )
    from_date = datetime.strptime(contrs["startedAt"], "%Y-%m-%dT%H:%M:%S%z")
    days_since = int((datetime.now(timezone.utc) - from_date) / timedelta(days=1))

    member_since = datetime.strptime(userdata["createdAt"], "%Y-%m-%dT%H:%M:%S%z")
    stats = f"""According to GitHub, I have submitted {pretty_count(userdata, "issues")} issues, {pretty_count(userdata, "pullRequests")} pull requests,
and also written {pretty_count(userdata, "issueComments")} issue comments here since {member_since.strftime("%Y")}.
Since then, my projects have been honored with a total of {counts["stargazerCount"]:,} \N{WHITE MEDIUM STAR} and {counts["forkCount"]:,} \N{FORK AND KNIFE}.
I am happy if you have found my software, code reviews, help, or feedback useful! \N{SMILING FACE WITH SMILING EYES AND THREE HEARTS}

Most of my Python projects are also available on the [Python Package Index](https://pypi.org/user/rytilahti/),
which according to the [PyPI Stats](https://pypistats.org/) have been downloaded {pypi_recent_count:,} times over the past month.
"""

    DEBUG_STR = "<!-- {debug} -->" if DEBUG else ""
    content = f"""
{DEBUG_STR}
### Hello! Hallo! Moi! \N{WAVING HAND SIGN}

I am Teemu from \N{REGIONAL INDICATOR SYMBOL LETTER F}\N{REGIONAL INDICATOR SYMBOL LETTER I}, and I'm currently living in \N{REGIONAL INDICATOR SYMBOL LETTER D}\N{REGIONAL INDICATOR SYMBOL LETTER E}, happy to see you here!

On this profile page, I present you some ([automatically generated](https://github.com/rytilahti/rytilahti)) information about my public contributions here on GitHub, 
mostly on projects useful for home automation.

{stats}

### My projects

GitHub says that I am currently a maintainer or a collaborator in the following projects:

{repos}

### Recent contributions

In the past {days_since} days (since {from_date.strftime(DATE_FORMAT)}), I have submitted {contrs["totalPullRequestContributions"]} pull requests on {contrs["totalRepositoriesWithContributedCommits"]} different repositories, including:
{pull_request_stats}


### Code Reviews

Besides contributing pull requests, I also try to help others by doing code reviews.
During the previously mentioned time period, I have submitted {contrs["totalPullRequestReviewContributions"]} reviews to pull requests on {contrs["totalRepositoriesWithContributedPullRequests"]} different repositories, including:
{code_review_stats}

(Generated on {datetime.now(timezone.utc).strftime(DATE_FORMAT)})
"""

    with open("README.md", "w") as f:
        f.write(content)


if __name__ == "__main__":
    asyncio.run(main())
