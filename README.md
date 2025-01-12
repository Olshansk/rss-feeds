I wrote a blog post about this repo here: https://olshansky.substack.com/p/no-rss-feed-no-problem-using-claude

# RSS Feed Generator <!-- omit in toc -->

You know how there are a bunch of blogs out there without RSS Feeds? 😡

Well, we're going to fix it Open Source Style. 🙌

To make it simple, it just uses GitHub actions and some Python code. 🐍

More importantly, we're using AI tooling so anyone can contribute. 🤖

And everyone can learn along the way. 🧑‍🎓

- [How do I subscribe to an existing RSS feed?](#how-do-i-subscribe-to-an-existing-rss-feed)
- [Which RSS feeds are available?](#which-rss-feeds-are-available)
- [How do I request a new RSS feed?](#how-do-i-request-a-new-rss-feed)
- [How do I contribute a new feed?](#how-do-i-contribute-a-new-feed)
- [What did I use to make this?](#what-did-i-use-to-make-this)
  - [1. GitHub Copilot Workspace](#1-github-copilot-workspace)
  - [2. Claude Projects](#2-claude-projects)
  - [3. Claude Sync](#3-claude-sync)
- [Star History](#star-history)
- [How does this work?](#how-does-this-work)

## How do I subscribe to an existing RSS feed?

To subscribe to an RSS feed, use the **raw** link of the feed file.

You can find all available feeds in the [feeds directory](./feeds).

For example, to subscribe to the Ollama Blog feed, use the following link:

```url
https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_ollama.xml
```

Personally, I use [Blogtrottr](https://blogtrottr.com/) so my email inbox acts
as an RSS queue, but you can use any RSS reader.

## Which RSS feeds are available?

- 🦙 [Ollama Blog](https://ollama.com/blog): [Ollama RSS feed](https://raw.githubusercontent.com/Olshansk/rss-feeds/refs/heads/main/feeds/feed_ollama.xml)
- 👨 [Paul Graham's Article](https://www.paulgraham.com/articles.html): [Paul Graham RSS feed](https://raw.githubusercontent.com/Olshansk/rss-feeds/refs/heads/main/feeds/feed_paulgraham.xml)
- 🦍 [Anthropic News](https://www.anthropic.com/news): [Anthropic RSS feed](https://raw.githubusercontent.com/Olshansk/rss-feeds/refs/heads/main/feeds/feed_anthropic.xml)
- 🤖 [OpenAI Research News](https://openai.com/news/research/): [OpenAI Research RSS feed](https://raw.githubusercontent.com/Olshansk/rss-feeds/refs/heads/main/feeds/feed_openai_research.xml)

Coming soon:

- 👨 [Patrick Collison's Blog](https://patrickcollison.com/culture)
- 💽 [Supabase Blog](https://supabase.com/blog)

## How do I request a new RSS feed?

If you would like to request a new RSS feed for a blog, please use our GitHub issue template.

Make sure to provide the link to the actual blog.

[Request a new RSS feed](https://github.com/Olshansk/rss-feeds/issues/new?template=request_rss_feed.md)

## How do I contribute a new feed?

To contribute a new feed, refer to the [Claude Projects](#claude-projects) section.

It provides detailed instructions on how to convert HTML files into Python scripts that generate RSS feeds.

## What did I use to make this?

### 1. GitHub Copilot Workspace

_Link: [GitHub Copilot Workspace](https://copilot-workspace.githubnext.com/)_

GitHub Copilot Workspace is still in preview (as of 01/2025), so I can't share the workspace.

However, I've attached the `copilot` label to all PRs generated by GitHub Copilot.

You can access them [here](https://github.com/Olshansk/rss-feeds/pulls?q=label%3Acopilot+).

### 2. Claude Projects

_Link: [Claude Projects](https://support.anthropic.com/en/articles/9517075-what-are-projects)_

I can't share the project (feature is not available as of 01/2025), so I'll share the details.

The knowledge of the project includes files from this repository.

The instructions are:

```text
The goal of this project is to generate rss (feed.xml) files from web pages (*.html) that contain blogs or updates but do not provide a subscribe button or a default RSS feed.

Here is the expected flow and instructions:

1. You will be given an HTML file that needs to be parsed and understood.

2. You will provide a python script that writes a `feed_{}.xml` file that is RSS feed compatible.

3. The `{}` in `feed_{}.xml` will refer to the name of a particular RSS feed.

4. GitHub actions will take care of triggering this periodically, so you don't have to worry about it

5. If you are not given an HTML file that you can parse into an rss feed, either ask for it or explain what the issue with the provided file is.
```

### 3. Claude Sync

Link: [Claude Sync](https://github.com/jahwag/ClaudeSync?tab=readme-ov-files)

I use `ClaudeSync` to sync all the files in this directory with the Project's knowledge.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Olshansk/rss-feeds&type=Date)](https://star-history.com/#Olshansk/rss-feeds&Date)

## How does this work?

```mermaid
flowchart TB
    subgraph GitHub["GitHub Repository"]
        action[[GitHub Action\nHourly Cron Job]]
        runner{{"run_all_feeds.py"}}
        feeds["Individual Feed Generators\n(*.py files)"]
        xml["Generated RSS Feeds\n(feed_*.xml)"]
    end

    subgraph External["External Services"]
        blogtrottr["Example: Blogtrottr"]
        rssreaders["Other RSS Readers"]
    end

    action -->|"Triggers"| runner
    runner -->|"Executes"| feeds
    feeds -->|"Scrapes"| websites[("Blog Websites\n(HTML Content)")]
    websites -->|"Content"| feeds
    feeds -->|"Generates"| xml
    xml -->|"Updates"| repo["GitHub Repository\nMain Branch"]

    repo -->|"Pulls Feed"| blogtrottr
    repo -->|"Pulls Feed"| rssreaders

    style GitHub fill:#e6f3ff,stroke:#0066cc
    style External fill:#f9f9f9,stroke:#666666
    style action fill:#ddf4dd,stroke:#28a745,color:#000000
    style runner fill:#fff3cd,stroke:#ffc107,color:#000000
    style feeds fill:#f8d7da,stroke:#dc3545,color:#000000
    style xml fill:#d1ecf1,stroke:#17a2b8,color:#000000
    style websites fill:#e2e3e5,stroke:#383d41,color:#000000
```
