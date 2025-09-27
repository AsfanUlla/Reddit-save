# Reddit-save
> Python script to download reddit post's and comments with media

## Pre-requisites
- yt-dlp
  - [Installation guide](https://github.com/yt-dlp/yt-dlp/wiki/Installation)
- Install python3, python3-venv
  - ```bash
    sudo apt install python3 python3-venv
    ```
- create Virtual Environment inside the project root folder and activate it
  - ```bash
    python3 -m venv venv
    . venv/bin/activate
    ```

## Install
```bash
pip install -r requirements.txt
```

## Run
```bash
python save.py -u <reddit_post_url>
```
```bash
python save.py -u <reddit_post_url> -d <destination_folder_path>
```
Help:
```bash
python save.py -h
```
