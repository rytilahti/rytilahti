import marimo

__generated_with = "0.10.0"
app = marimo.App()


@app.cell
def __():
    import asyncio
    import string
    from gql import Client, gql
    from gql.transport.aiohttp import AIOHTTPTransport
    from datetime import datetime, timedelta
    from pprint import pprint as pp, pformat as pf
    import os
    import sys
    import logging
    import pypistats
    import json

    DEBUG = 0
    try:
        TOKEN = os.environ["TOKEN"]
        DEBUG = os.environ.get("DEBUG", 0)
    except:
        with open(".token") as f:
            TOKEN = f.read().strip()

    SUMMARIZE_AFTER_COUNT = 5
    DATE_FORMAT = "%d %B, %Y"
    return (
        AIOHTTPTransport,
        Client,
        DATE_FORMAT,
        DEBUG,
        SUMMARIZE_AFTER_COUNT,
        TOKEN,
        asyncio,
        datetime,
        gql,
        json,
        logging,
        os,
        pf,
        pp,
        pypistats,
        string,
        sys,
        timedelta,
    )


@app.cell
def __(json, pypistats):
    PYPI_PACKAGES = [
        "python-miio",
        "python-kasa",
        "pyHS100",
        "python-eq3bt",
        "python-yeelightbt",
        "python-songpal",
        "python-mirobo",
    ]
    # monthly stats here just for reference, last_week is also available.
    pypi_recent = {
        package: json.loads(pypistats.recent(package, format="json"))["data"]["last_month"]
        for package in PYPI_PACKAGES
    }
    pypi_recent_count = sum(pypi_recent.values())
    pypi_totals = {
        package: json.loads(pypistats.overall(package, mirrors=False, format="json"))["data"][0]["downloads"]
        for package in PYPI_PACKAGES
    }
    pypi_totals_count = sum(pypi_totals.values())
    return (
        PYPI_PACKAGES,
        pypi_recent,
        pypi_recent_count,
        pypi_totals,
        pypi_totals_count,
    )


@app.cell
def __(AIOHTTPTransport, Client, SUMMARIZE_AFTER_COUNT, TOKEN, gql, logging):
    async def fetch_data(query):
        transport = AIOHTTPTransport(
            url="https://api.github.com/graphql",
            headers={"Authorization": f"bearer {TOKEN}"},
        )

        async with Client(
            transport=transport,
            fetch_schema_from_transport=True,
        ) as session:
            _query = gql(query)

            result = await session.execute(_query)
            return result

    def pretty_project(project):
        return f'[{project["nameWithOwner"]} \N{EN DASH} {project["description"]}]({project["url"]}) ({project["stargazerCount"]:,} \N{WHITE MEDIUM STAR}, {project["forkCount"]:,} \N{FORK AND KNIFE})'

    def get_contributions_list(
        contributions, count=SUMMARIZE_AFTER_COUNT, contribution_type="contributions"
    ):
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

    def get_repos(userdata, count=SUMMARIZE_AFTER_COUNT):
        output = ""
        idx = 0
        logging.info("Found %s repositories", len(userdata["repositories"]["nodes"]))
        ignored_repos = ["rytilahti/rytilahti", "rytilahti/.github"]
        for project in userdata["repositories"]["nodes"]:
            if project["nameWithOwner"] in ignored_repos:
                continue
            if idx == count:
                output += "\n<details><summary>Show more</summary><p>\n\n"
            output += f"{idx+1}. {pretty_project(project)}\n"
            idx += 1

        if not output:
            print(userdata["repositories"]["nodes"])
            logging.error(userdata["repositories"]["nodes"])
            #raise Exception("Unable to download repo information")

        output += "</p></details>"

        return output

    def pretty_count(user, var):
        count = user[var]["totalCount"]
        return f"{count:,}"

    return fetch_data, get_contributions_list, get_repos, pretty_count, pretty_project


@app.cell
async def __(fetch_data):
    with open("github_query.graphql") as f:
        _q = f.read()
    data = await fetch_data(_q)

    userdata = data["user"]
    return data, userdata


@app.cell
def __(datetime, get_contributions_list, get_repos, timedelta, userdata):
    from collections import defaultdict

    # prepare repos, contributions & stats
    contrs = userdata["contributionsCollection"]

    repos = get_repos(userdata)

    def get_counts(_userdata):
        keys = ["stargazerCount", "forkCount"]
        res = defaultdict(lambda: 0)
        for repo in _userdata["repositories"]["nodes"]:
            for k in keys:
                res[k] += repo[k]
        return res

    counts = get_counts(userdata)

    pull_request_stats = get_contributions_list(
        contrs["pullRequestContributionsByRepository"], contribution_type="pull requests"
    )
    code_review_stats = get_contributions_list(
        contrs["pullRequestReviewContributionsByRepository"], contribution_type="reviews"
    )

    from_date = datetime.strptime(contrs["startedAt"], "%Y-%m-%dT%H:%M:%S%z")
    days_since = int(
        ((datetime.utcnow() - from_date.replace(tzinfo=None)) / timedelta(days=1))
    )
    return (
        code_review_stats,
        contrs,
        counts,
        days_since,
        defaultdict,
        from_date,
        get_counts,
        pull_request_stats,
        repos,
    )


@app.cell
def __(counts, datetime, pretty_count, pypi_recent_count, userdata):
    member_since = datetime.strptime(userdata["createdAt"], "%Y-%m-%dT%H:%M:%S%z")
    stats = f"""According to GitHub, I have submitted {pretty_count(userdata, "issues")} issues, {pretty_count(userdata, "pullRequests")} pull requests,
and also written {pretty_count(userdata, "issueComments")} issue comments here since {member_since.strftime("%Y")}.
Since then, my projects have been honored with a total of {counts["stargazerCount"]:,} \N{WHITE MEDIUM STAR} and {counts["forkCount"]:,} \N{FORK AND KNIFE}.
I am happy if you have found my software, code reviews, help, or feedback useful! \U0001f970

Most of my Python projects are also available on the [Python Package Index](https://pypi.org/user/rytilahti/),
which according to the [PyPI Stats](https://pypistats.org/) have been downloaded {pypi_recent_count:,} times over the past month.
"""
    return member_since, stats


@app.cell
def __(userdata):
    OPEN_TO_WORK = "**I am currently looking for new opportunities, [feel free to get in touch!](https://linkedin.com/in/teemurytilahti)**" if userdata["isHireable"] else ""
    return (OPEN_TO_WORK,)


@app.cell
def __(
    DATE_FORMAT,
    DEBUG,
    OPEN_TO_WORK,
    code_review_stats,
    contrs,
    datetime,
    days_since,
    from_date,
    pull_request_stats,
    repos,
    stats,
):
    DEBUG_STR = "<!-- {debug} -->" if DEBUG else ""
    content = f"""
{DEBUG_STR}
### Hello! Hallo! Moi! \N{WAVING HAND SIGN}

I am Teemu from \U0001f1eb\U0001f1ee, and I'm currently living in \U0001f1e9\U0001f1ea, happy to see you here! {OPEN_TO_WORK}

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

(Generated on {datetime.utcnow().strftime(DATE_FORMAT)})
"""

    with open("README.md", "w") as f:
        f.write(content)

    return (content,)


@app.cell
def __(content):
    import marimo as mo

    return mo.md(content)


if __name__ == "__main__":
    app.run()
