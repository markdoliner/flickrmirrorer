Overview
========
A small command-line python script that creates a local backup of your
Flickr data. It mirrors images, videos, titles, description, tags,
albums and collections.

Available at https://github.com/markdoliner/flickrmirrorer


Requirements
============
* python 2.something or python 3.anything
* python dateutil
  * Ubuntu: apt-get install python-dateutil
* python flickrapi library 2.0 or newer.
  * Homepage: http://stuvel.eu/flickrapi
  * Ubuntu 16.04 LTS Xenial and newer: apt-get install python-flickrapi
* python requests


Usage
=====
The script was developed on Linux. It should work on other Unixy operating
systems such as OS X, hopefully without changes. It could probably be made
to work on Microsoft Windows with minor changes.

<pre>
e.x. ./flickrmirrorer.py /mnt/backup/flickr/
</pre>

Features
========
The script allows you to mirror only photos or only videos. See the ```--ignore-videos``` and ```--ignore-photos``` command line options.

Your local backup can be cleaned automatically, by deleting what is no longer in Flickr. This option is disabled by default. See the ```--clean``` command line option.

The mirroring process is time-stamped. This allows FlicrkMirrorer to resume the process from the previously reached moment in time. (It makes use of Flickr's API upload date parameter.) This approach is particularly useful when having a large Flickr photostream. The time-stamp is stored in a local file, which you can manually modify (or even delete), if needed.

The script outputs statistics that summarize its work progress. You can enable this option using ```-s``` from the command line. Statistics are also displayed in case the script is interrupted.

Running via Cron
================
Running this script regularly via cron is a good way to keep your backup
up to date.  For example, create the file /etc/cron.d/flickr_backup
containing the following:

<pre>
# Run Flickr photo mirroring script.
# Sleep between 0 and 4 hours to distribute load on Flickr's API servers.
0 3 * * 2  root  sleep $((`bash -c 'echo $RANDOM'` \% 14400)) && /usr/local/bin/flickrmirrorer.py -q /mnt/backup/flickr/
</pre>

If you run the cronjob as a user other than yourself you may
need to take additional steps to make sure the cron user is able to
authenticate.  The steps are something like this:

1. Run the script as yourself the first time around.  It should pop open
   your web browser and request permission.
2. After granting permission an authorization token is stored in
   ~/.flickr/9c5c431017e712bde232a2f142703bb2/auth.token
3. Copy this file to the home directory of the cron user:
<pre>
sudo mkdir -p /root/.flickr/9c5c431017e712bde232a2f142703bb2/
sudo cp ~/.flickr/9c5c431017e712bde232a2f142703bb2/auth.token \
        /root/.flickr/9c5c431017e712bde232a2f142703bb2/auth.token
</pre>


Output
======
The script creates this directory hierarchy:
<pre>
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
</pre>

The metadata files contain JSON data dumped from the Flickr API.
It's not the prettiest thing in the world... but it does contain
all the necessary data in case you want to recover from it.

The album and collection directories contain symlinks to the files in
the photostream. The symlink names in albums are numbered so as to
preserve the order.

Routine status is printed to stdout by default.
Errors are printed to stderr.
To see more options run with the --help flag.


Running unit tests
==================
Run [`py.test`](http://pytest.org/).


TODO
====
* Mirror comments
* Store order of photos in photostream
* Store order of albums in collections
