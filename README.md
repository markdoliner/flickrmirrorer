Overview
========
A small command-line python script that creates a local backup of your
Flickr data. It mirrors images, video metadata, titles, description, tags,
albums and collections.

Available at https://github.com/markdoliner/flickrmirrorer

Note that if you just want to download your Flickr data once you can use
the "Request my Flickr data" button at the bottom of
https://www.flickr.com/account — this script is intended for keeping a
local copy of your Flickr data updated on an ongoing basis.

Usage
=====
The script was developed on Linux. It should work on other Unixy operating
systems like macOS, hopefully without changes. It could probably be made
to work on Microsoft Windows with minor changes.

One time setup:

```
git clone https://github.com/markdoliner/flickrmirrorer
cd flickrmirrorer
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then run this to backup your Flickr data:

```
.venv/bin/python flickrmirrorer.py /mnt/backup/flickr/
```

(Replace `/mnt/backup/flickr` with the path to your backup)

The first time you run this command, it will open your web browser and request permission from Flickr.

See `--help` for options.


Features
========
The script allows you to mirror only photos, only videos, or both. See
the `--ignore-videos` and `--ignore-photos` command line options.

Your local backup can be cleaned automatically, so that files that were
deleted in Flickr are deleted locally. Deletion is disabled by default. See
the `--delete-unknown` command line option.

The script displays a summary of its actions if `--statistics` is passed on
the command line.

Requirements
============

(These are covered by running `pip install -r requirements.txt` as mentioned above)

* python 3
* python dateutil
* python flickrapi library 2.0 or newer.
  * Homepage: https://stuvel.eu/software/flickrapi/
* python requests

Running via Cron
================
Running this script regularly via cron is a good way to keep your backup
up to date. On Linux you can use `crontab -e` to configure per-user cron jobs:

```
# Run Flickr photo mirroring script.
# Sleep between 0 and 4 hours to distribute load on Flickr's API servers.
0 3 * * 2  root  sleep $((`bash -c 'echo $RANDOM'` \% 14400)) && /home/my_user/flickrmirrorer/.venv/bin/python flickrmirrorer.py --quiet /mnt/backup/flickr/
```

When using per-user cron jobs you shouldn't need to do anything special to
allow the script to authenticate. However, if you run it as a system-wide
cron job and it runs as a user other than yourself then you will
need to take additional steps to make sure the cron user is able to
authenticate. The steps are something like this:

1. Run the script as yourself the first time around. It should open
   your web browser and request permission.
2. After granting permission an authorization token is stored in
   `~/.flickr/oauth-tokens.sqlite`
3. Copy this file to the home directory of the cron user:
   ```
   sudo mkdir -p /root/.flickr/
   sudo cp ~/.flickr/oauth-tokens.sqlite /root/.flickr/oauth-tokens.sqlite
   ```


Output
======
The script creates this directory hierarchy:

```
dest_dir
dest_dir/photostream/
dest_dir/photostream/12345.jpg
dest_dir/photostream/12345.jpg.metadata
dest_dir/photostream/12346.jpg
dest_dir/photostream/12346.jpg.metadata
dest_dir/photostream/12347.jpg
dest_dir/photostream/12347.jpg.metadata
dest_dir/Not in any album/
dest_dir/Not in any album/12345.jpg -> ../photostream/12345.jpg
dest_dir/Albums/
dest_dir/Albums/Waterfalls - 6789/
dest_dir/Albums/Waterfalls - 6789/1_12346.jpg -> ../../photostream/12346.jpg
dest_dir/Albums/Waterfalls - 6789/2_12347.jpg -> ../../photostream/12347.jpg
dest_dir/Collections/
dest_dir/Collections/Nature - 2634-98761234/Waterfalls - 6789 -> ../../Albums/Waterfalls - 6789
dest_dir/Collections/Nature - 2634-98761234/Mountains - 6790  -> ../../Albums/Mountains - 6790
```

The metadata files contain JSON data dumped from the Flickr API.
It's not the prettiest thing in the world... but it does contain
all the necessary data in case you want to recover from it.

The album and collection directories contain symlinks to the files in
the photostream. The symlink names in albums are numbered so as to
preserve the order.

Routine status is printed to stdout by default.

Errors are printed to stderr.

To see more options run with the `--help` flag.


A note about videos
===================
The Flickr API does not support downloading original video files. If this
script encounters videos in your photostream, it asks you download them
(you must be logged in to your Flickr account).


Running unit tests
==================
Run `python -m unittest`


TODO
====
* Handle download errors better:
  * Add retry logic.
  * Continue trying to download other photos.
  * Stop running only if there are many download errors.
* Mirror comments
* Store order of photos in photostream
* Store order of albums in collections


Changes
=======
2023-12-27
- Drop support for Python 2.
- Change tests to use standard Python unittest library instead of pytest.
- Update documentation to suggest using a venv.

2018-06-02
- Support for nested collections and empty collections.

2017-01-02
- Don't warn about downloading videos if they've already been downloaded.
- Unknown files are no longer deleted by default.
- Added new command line option `--delete-unknown`
- Added new command line option `--ignore-photos`
- Added new command line option `--ignore-videos`
- Print statistics even if script is killed by CTRL+C.
