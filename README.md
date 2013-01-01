About
=====
A small command-line python script that creates a local backup of your
Flickr data.  It mirrors images, titles, description, tags and sets.

Available at https://github.com/markdoliner/flickrmirrorer


Requirements
============
* python 2.something
* python flickrapi library.
  * Homepage: http://stuvel.eu/flickrapi
  * Ubuntu: apt-get install python-flickrapi


Usage
=====
e.x. ./flickrmirrorer /mnt/backup/flickr/

You may want to run this from cron.


Output
======
Creates this directory hierarchy:
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
dest_dir/Set 6789 - Pretty Waterfalls/12346.jpg -> ../photostream/12346.jpg
dest_dir/Set 6789 - Pretty Waterfalls/12347.jpg -> ../photostream/12347.jpg
</pre>

Routine status is printed to stdout.
Errors are printed to stderr.
