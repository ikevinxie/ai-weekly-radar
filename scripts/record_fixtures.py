"""录制真实 API 响应到 tests/fixtures/，供离线测试使用。

用法: python3 scripts/record_fixtures.py [source ...]   # 不带参数录全部
"""
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from collector.net import fetch_text  # noqa: E402
from collector.sources import arxiv, github, hackernews, huggingface, producthunt, reddit  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures"
TODAY = datetime.date.today()

RECIPES = {
    "github": [("github_search.json", lambda: fetch_text(github.urls(TODAY)[0]))],
    "hackernews": [("hackernews_search.json", lambda: fetch_text(hackernews.urls(TODAY)[0]))],
    "producthunt": [("producthunt_feed.xml", lambda: fetch_text(producthunt.FEED_URL))],
    "arxiv": [("arxiv_feed.xml", lambda: fetch_text(arxiv.url(TODAY)))],
    "huggingface": [
        ("huggingface_spaces.json", lambda: fetch_text(huggingface.SPACES_URL)),
        ("huggingface_papers.json", lambda: fetch_text(huggingface.PAPERS_URL)),
    ],
    "reddit": [("reddit_top.rss", lambda: fetch_text(reddit.urls(TODAY)[1]))],
}


def main():
    targets = sys.argv[1:] or list(RECIPES)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    failures = []
    for name in targets:
        for filename, grab in RECIPES[name]:
            try:
                text = grab()
                (FIXTURES / filename).write_text(text, encoding="utf-8")
                print(f"ok   {filename}  ({len(text)} bytes)")
            except Exception as e:
                failures.append(name)
                print(f"FAIL {filename}: {e}")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
