import tldextract
from urllib.parse import urlparse
import requests
from pathlib import Path
from datetime import datetime
from yt_dlp import YoutubeDL
from fake_useragent import UserAgent

class DownloadMedia:
    def __init__(self, submission, destination: Path) -> None:
        self.submission = submission
        self.destination = destination.joinpath("media")

        self.downloaded_files = dict(
            images=[],
            videos=[]
        )

        media_urls = self.extract_media_url()
        if media_urls.get("images"):
            self.download_images(media_urls.get("images"))

        if media_urls.get("videos"):
            self.download_videos(media_urls.get("videos"))


    def get_downloaded_media(self):
        return self.downloaded_files

    def download_images(self, urls):
        for url in urls:
            try:
                parsed_url = urlparse(url)
                filename = Path(parsed_url.path).name
                file_path = Path.joinpath(self.destination ,filename)

                headers = {"User-Agent": UserAgent().random}
                response = requests.get(url, stream=True, headers=headers)

                if response.status_code == 200:
                    self.destination.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'wb') as out_file:
                        for chunk in response.iter_content(1024):
                            out_file.write(chunk)
                    print(f"✅ Downloaded Media: {filename}")
                    self.downloaded_files["images"].append(file_path)
                else:
                    print(f"❌ Failed to download {url} (status code {response.status_code})")
                    continue
            except Exception as e:
                print(f"⚠️ Error downloading {url}: {e}")
                continue

    def ytdl_progress_hook(self, d):
        if d['status'] == 'finished':
            if d["info_dict"]["filename"] not in self.downloaded_files["videos"]:
                self.downloaded_files["videos"].append(d["info_dict"]["filename"])

    def download_videos(self, urls):
        ydl_opts = dict(
            nopart=True,
            retries=10,
            fragment_retries=10,
            no_overwrites=True,
            no_warnings=True,
            restrictfilenames=True,
            quiet=True,
            consoletitle=True,
            format="bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            writethumbnail=True,
            writesubtitles=True,
            writeautomaticsub=True,
            subtitlesformat='srt',
            subtitleslangs='eng',
            merge_output_format='mp4',
            outtmpl='%(title)s_[%(id)s].%(ext)s',
            paths=dict(home=str(self.destination)),
            progress_hooks=[self.ytdl_progress_hook]
        )

        try:
            with YoutubeDL(ydl_opts) as ydl:
                print("▶️ Downloading Media: Video...")
                ydl.download(urls)
        except Exception as e:
            print(f"⚠️ Error downloading: {e}")


    def extract_media_url(self):
        media_urls = dict(
            images=[],
            videos=[]
        )

        ROOT_IMAGE_URL = "https://i.redd.it"
        ROOT_VIDEO_URL = "https://v.redd.it"

        media_url = self.submission.get('url_overridden_by_dest') or self.submission.get('url')
        if media_url and any(media_url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            media_urls["images"].append(media_url)

        if self.submission.get("domain") in ["v.redd.it", "youtube.com", "youtu.be"]:
            media_urls["videos"].append(media_url)

        if self.submission.get("domain") == "reddit.com" and self.submission.get("gallery_data"):
            for item in self.submission.get("gallery_data")["items"]:

                try:
                    # Media Metadata
                    media_meta = self.submission["media_metadata"][item["media_id"]]

                    # get media preview url u=Image, gif=GIF
                    preview_url = media_meta["s"].get("u", media_meta["s"].get("gif"))

                    if not preview_url:
                        continue

                    parsed_preview_url = urlparse(preview_url)
                    media_type = media_meta.get("e")

                    if media_type in ["Image", "AnimatedImage"]:
                        url = f"{ROOT_IMAGE_URL}{parsed_preview_url.path}"
                        media_urls["images"].append(url)

                    elif media_type == "Video":
                        url = f"{ROOT_VIDEO_URL}{parsed_preview_url.path}"
                        media_urls["videos"].append(url)

                    else:
                        url = f"{parsed_preview_url.scheme}://{parsed_preview_url.netloc}{parsed_preview_url.path}"
                        media_urls["images"].append(url)

                except KeyError as e:
                    print("KeyError: {}".format(e))
                    continue
                except Exception as e:
                    print(e)
                    continue

        return media_urls
