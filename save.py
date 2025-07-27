from math import perm
import requests
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlparse, parse_qs
import argparse
import markdown
import tldextract

from download_media import DownloadMedia

ROOT_DOMAIN = "https://www.reddit.com"

def is_valid_reddit_url(url: str) -> bool:
    try:
        parsed_url = urlparse(url)
        domain_parts = tldextract.extract(parsed_url.netloc)
        domain = f"{domain_parts.domain}.{domain_parts.suffix}"

        # Check if it's a Reddit domain and path includes 'comments'
        if domain == "reddit.com" and "comments" in parsed_url.path:
            return True
        return False
    except Exception:
        return False

def parse_reddit_url(url):
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")

    submission_id = None
    comment_id = None
    context = 1

    if "comments" in path_parts:
        idx = path_parts.index("comments")
        submission_id = path_parts[idx + 1]
        if len(path_parts) > idx + 3:
            comment_id = path_parts[idx + 3]

    query_params = parse_qs(parsed.query)
    if "context" in query_params:
        try:
            context = int(query_params["context"][0])
        except ValueError:
            pass

    return submission_id, comment_id, context


def render_comment(comment, depth=0):
    author = escape(comment.get("author", "[deleted]"))
    # print(comment.get("body", ""))
    body = escape(comment.get("body", ""))
    score = comment.get("score", 0)
    created_utc = comment.get("created_utc")
    permalink = ROOT_DOMAIN + comment.get('permalink', '')
    authorlink = ROOT_DOMAIN + "/u/" + author
    time_str = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if created_utc else "N/A"

    html = f'''
<div class="comment-box depth-{depth}">
    <div class="comment-header">
        <div><a href="{authorlink}" target="_blank">u/{author}</a>, on {time_str} ({score}) : <a href="{permalink}" target="_blank">Permalink</a></div>
    </div>
    <div class="comment-body">{body}</div>
'''

    for reply in comment.get("replies", []):
        html += render_comment(reply, depth + 1)

    html += "</div>"
    return html


def flatten_replies(comment_data):
    replies = []
    raw_replies = comment_data.get("replies")
    if isinstance(raw_replies, dict):
        children = raw_replies.get("data", {}).get("children", [])
        for child in children:
            if child.get("kind") == "t1":
                cdata = child["data"]
                cdata["replies"] = flatten_replies(cdata)
                replies.append(cdata)
    return replies

def fetch_media(submission_data, dest_dir: Path):
    output_dir = ""
    attached_media = submission_data.get("url") or submission_data.get('url_overridden_by_dest')

    if urlparse(attached_media).path != submission_data.get("permalink"):
        output_dir = dest_dir.joinpath(
            f"{submission_data["permalink"].split('/')[-2][:150]}-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        media_files = DownloadMedia(
            submission=submission_data,
            destination=output_dir
        ).get_downloaded_media()

        if media_files.get("images") or media_files.get("videos"):
            attached_media = media_files
        else:
            output_dir = ""
    else:
        attached_media = None

    return attached_media, output_dir

def fetch_comment_thread(submission_id, comment_id=None, context=1):
    if comment_id:
        url = f"{ROOT_DOMAIN}/comments/{submission_id}/_/{comment_id}.json?context={context}"
    else:
        url = f"{ROOT_DOMAIN}/comments/{submission_id}.json"

    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    res.raise_for_status()

    data = res.json()
    submission_data = data[0]["data"]["children"][0]["data"]
    comments = []

    threads = data[1]["data"]["children"]
    for item in threads:
        if item["kind"] == "t1":
            c = item["data"]
            c["replies"] = flatten_replies(c)
            comments.append(c)

    submission_body_html = markdown.markdown(submission_data.get("selftext", ""), extensions=["extra", "nl2br"])
    created_utc = submission_data.get("created_utc")
    if created_utc:
        created_utc = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

    html_data = {
        "submission": {
            "title": "{} - {}".format(submission_data.get("subreddit_name_prefixed"), submission_data.get("title")),
            "permalink": ROOT_DOMAIN + submission_data.get("permalink", "[deleted]"),
            "author": submission_data.get("author", "[deleted]"),
            "author_link": ROOT_DOMAIN + "/u/" + submission_data.get("author", "[deleted]"),
            "score": submission_data.get("score"),
            "created_at": created_utc,
            "selftext": submission_body_html,
        },
        "comments": comments
    }

    return submission_data, html_data


def render_html(data, dest_dir: Path, filename, output_dir):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("thread.jinja")

    rendered_comments = [render_comment(c) for c in data["comments"]]
    output = template.render(submission=data["submission"], comments=rendered_comments)

    dest_dir = dest_dir.joinpath(output_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{filename}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.html"
    save_path = Path.joinpath(dest_dir, filename)
    save_path.write_text(output, encoding="utf-8")

    print(f"✅ Saved to {save_path}")

def main():
    parser = argparse.ArgumentParser(description="Download Reddit post and comments with context.")
    parser.add_argument("-u", "--url", required=True, help="Reddit post or comment URL")
    parser.add_argument("-d", "--destination", type=Path, default=Path.cwd(), help="Output directory (default: current working directory)")
    args = parser.parse_args()

    url = args.url
    if not is_valid_reddit_url(url):
        raise ValueError(f"❌ Invalid Reddit URL: {url}")

    dest_dir = args.destination.resolve()

    sub_id, com_id, context = parse_reddit_url(url)
    submission_data, html_data = fetch_comment_thread(sub_id, com_id, context)
    attached_media, output_dir = fetch_media(submission_data, dest_dir)

    # update html_data with attached media
    if attached_media:
        html_data["submission"]["attached_media"] = attached_media

    # get file name from permalink and keep the max lenght to 150
    filename = submission_data.get("permalink",
        submission_data.get("title", "reddit_post")
    ).split('/')[-2][:150]
    render_html(html_data, dest_dir, filename, output_dir)

if __name__ == "__main__":
    main()
