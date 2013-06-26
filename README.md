About
=====
A small command-line python script that creates a local backup of your
Flickr data.  It mirrors images, titles, description, tags, sets and
collections.

Available at https://github.com/markdoliner/flickrmirrorer


Requirements
============
* python 2.something
* python flickrapi library.
  * Homepage: http://stuvel.eu/flickrapi
  * Ubuntu: apt-get install python-flickrapi


Usage
=====
<pre>
e.x. ./flickrmirrorer /mnt/backup/flickr/
</pre>

Running via Cron
================
Running this script regularly via cron is a good way to keep your backup
up to date.  For example, create the file /etc/cron.d/flickr_backup
containing the following:

<pre>
# Run Flickr photo mirroring script.
# Sleep between 0 and 4 hours to distribute load on Flickr's API servers.
0 3 * * 2  root  sleep $((`bash -c 'echo $RANDOM'` \% 14400)) && /usr/local/bin/flickrmirrorer -q /mnt/backup/flickr/
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
dest_dir/Not in any set/
dest_dir/Not in any set/12345.jpg -> ../photostream/12345.jpg
dest_dir/Set 6789 - Pretty Waterfalls/
dest_dir/Set 6789 - Pretty Waterfalls/1_12346.jpg -> ../photostream/12346.jpg
dest_dir/Set 6789 - Pretty Waterfalls/2_12347.jpg -> ../photostream/12347.jpg
</pre>

The metadata files contain JSON data dumped from the Flickr API.
It's not the prettiest thing in the world... but it does contain
all the necessary data in case you want to recover from it.

Routine status is printed to stdout.
Errors are printed to stderr.


TODO
====
* Mirror comments
* Store order of photos in photostream
* Store order of sets in collections
* Remove local sets and collections that have been removed from Flickr
