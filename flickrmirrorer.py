#!/usr/bin/env python

# A small command-line python script that creates a local backup of your
# Flickr data.  It mirrors images, titles, description, tags, albums and
# collections.
#
# Available at https://github.com/markdoliner/flickrmirrorer
#
# Licensed as follows (this is the 2-clause BSD license, aka
# "Simplified BSD License" or "FreeBSD License"):
#
# Copyright (c)
#   Johan Walles, 2016
#   Mark Doliner, 2012-2016
#   Mattias Holmlund, 2013
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# - Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# - Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import argparse
import errno
import math
import os
import pkg_resources
import requests
import shutil
import six
import sys
import webbrowser
from six.moves import urllib
import dateutil.parser
import datetime
import time

try:
    # We try importing simplejson first because it's faster than json
    # in python 2.7 and lower
    import simplejson as json
except ImportError:
    import json

try:
    import flickrapi
except ImportError:
    sys.stderr.write('Error importing flickrapi python library.  Is it installed?\n')
    sys.exit(1)

API_KEY = '9c5c431017e712bde232a2f142703bb2'
API_SECRET = '7c024f6e7a36fc03'

PLEASE_GRANT_AUTHORIZATION_MSG = """
Please authorize Flickr Mirrorer to read your photos, titles, tags, etc.

1. Visit %s
2. Click "OK, I'LL AUTHORIZE IT"
3. Copy and paste the code here and press 'return'

"""

NUM_PHOTOS_PER_BATCH = 500


class VideoDownloadError(Exception):
    def __str__(self):
        return '%s' % self.args[0]


def _check_flickrapi_version():
    flickrapi_version = pkg_resources.get_distribution('flickrapi').version
    if pkg_resources.parse_version(flickrapi_version) < pkg_resources.parse_version('2.0'):
        sys.stderr.write(
            'Error: The installed version of the flickrapi python \n'
            '       library (%s) is too old. 2.0 or newer is required.\n' % flickrapi_version)
        sys.exit(1)


def _ensure_dir_exists(path):
    """Create the directory 'path' if it does not exist.
    Calls sys.exit(1) if any directory could not be created."""
    try:
        os.makedirs(path)
    except OSError as ex:
        if ex.errno != errno.EEXIST:
            sys.stderr.write('Error creating destination directory %s: %s\n'
                             % (path, ex.strerror))
            sys.exit(1)


def _ensure_dir_doesnt_exist(path):
    """Remove the directory 'path' and all contents if it exists.
    Calls sys.exit(1) if the directory or any contents could not be removed."""
    try:
        shutil.rmtree(path)
    except OSError as ex:
        if ex.errno != errno.ENOENT:
            sys.stderr.write('Error removing %s: %s\n' % (path, ex.strerror))
            sys.exit(1)


def _validate_json_response(rsp):
    """Exits the script with an error if the response is a failure.

    Args:
       rsp (dict): A parse JSON response from the Flickr API.
    """
    if rsp['stat'] != 'ok':
        sys.stderr.write('API request failed: Error %(code)s: %(message)s\n' % rsp)
        sys.exit(1)


def test_known_timestamp():
    timestamp = _get_timestamp({
        'datetakenunknown': '0',
        'datetaken': '2015-11-02 12:35:07'
    })
    assert timestamp.isoformat() == "2015-11-02T12:35:07"


def test_plain_title_timestamp():
    timestamp = _get_timestamp({
        'datetakenunknown': '1',
        'datetaken': '2014-10-01 13:45:37',
        'title': '20151130_135610'
    })
    assert timestamp.isoformat() == "2015-11-30T13:56:10"


def test_unparseable_title_timestamp():
    timestamp = _get_timestamp({
        'datetakenunknown': '1',
        'datetaken': '2014-10-01 13:45:37',
        'title': 'flaskpost'
    })

    # Fall back on datetaken if we can't parse the date from the title
    assert timestamp.isoformat() == "2014-10-01T13:45:37"


def _get_timestamp(photo):
    """
    Return photo timestamp, get it from:
    1. datetaken unless datetakenunknown
    2. parse from photo title 'YYYYMMDD_HHmmss'
    3. datetaken anyway; it's available even if unknown, so we just go with
    whatever Flickr made up for us
    """
    if photo['datetakenunknown'] == "0":
        return dateutil.parser.parse(photo['datetaken'])

    try:
        parsed = datetime.datetime.strptime(photo['title'], '%Y%m%d_%H%M%S')
        if parsed.year > 2000 and parsed < datetime.datetime.now():
            return parsed
    except ValueError:
        # Unable to parse photo title as datetime
        pass

    return dateutil.parser.parse(photo['datetaken'])


class FlickrMirrorer(object):
    dest_dir = None
    photostream_dir = None
    tmp_filename = None
    flickr = None

    def __init__(self, dest_dir, verbosity, print_statistics, include_views):
        self.dest_dir = dest_dir
        self.verbosity = verbosity
        self.print_statistics = print_statistics
        self.include_views = include_views
        self.photostream_dir = os.path.join(self.dest_dir, 'photostream')
        self.old_albums_dir = os.path.join(self.dest_dir, 'Sets')
        self.albums_dir = os.path.join(self.dest_dir, 'Albums')
        self.collections_dir = os.path.join(self.dest_dir, 'Collections')
        self.tmp_filename = os.path.join(self.dest_dir, 'tmp')

        # Statistics
        self.deleted_photos = 0
        self.modified_photos = 0
        self.new_photos = 0
        self.modified_albums = 0
        self.modified_collections = 0

        # Create flickrapi instance
        self.flickr = flickrapi.FlickrAPI(api_key=API_KEY, secret=API_SECRET, format='parsed-json')

    def run(self):
        try:
            self._run_helper()
        finally:
            self._cleanup()

    def _run_helper(self):
        # Authenticate
        # The user-friendly way to do this is with this command:
        #     self.flickr.authenticate_via_browser(perms='read')
        # However, the nature of this script is such that we don't want
        # to rely on people running it somwhere with a web browser
        # installed. So use the manual authentication process. A
        # reasonable compromise might be to try browser auth first and
        # if it fails then fall back to manual auth. Really flickrapi
        # should do that for us. Or at least print the URL to the
        # console.
        if not self.flickr.token_valid(perms=six.u('read')):
            self.flickr.get_request_token(oauth_callback=six.u('oob'))
            authorize_url = self.flickr.auth_url(perms=six.u('read'))
            webbrowser.open_new_tab(authorize_url)

            # Use input on python 3 and newer. Use raw_input for
            # backward compatability with older python.
            try:
                verifier = raw_input(PLEASE_GRANT_AUTHORIZATION_MSG % authorize_url)
            except NameError:
                verifier = input(PLEASE_GRANT_AUTHORIZATION_MSG % authorize_url)

            self.flickr.get_access_token(six.u(verifier))

        # Create destination directory
        _ensure_dir_exists(self.dest_dir)

        # Fetch photos
        self._download_all_photos()

        # Rename the albums directory from "Sets" to "Albums," if applicable.
        # This is only needed to migrate people who used older versions of
        # this script. It can be removed once everyone has been migrated.
        # TODO: Remove this and the old_albums_dir variable at some point. It
        # was added on 2014-12-14. Maybe remove it a year later?
        if os.path.isdir(self.old_albums_dir):
            if os.path.exists(self.albums_dir):
                sys.stderr.write(
                    'Error: Wanted to rename %s to %s, but the latter '
                    'already exists. Please remove one of these.\n'
                    % (self.old_albums_dir, self.albums_dir))
                sys.exit(1)
            os.rename(self.old_albums_dir, self.albums_dir)

        # Create albums and collections
        self._mirror_albums()
        self._create_not_in_any_album_dir()
        self._mirror_collections()

        if self.print_statistics:
            print('New photos: %d' % self.new_photos)
            print('Deleted photos: %d' % self.deleted_photos)
            print('Modified photos: %d' % self.modified_photos)
            print('Modified albums: %d' % self.modified_albums)
            print('Modified collections: %d' % self.modified_collections)

    def _download_all_photos(self):
        """Download all our pictures and metadata.
        If you have a lot of photos then this function will take a while."""

        self._verbose('Fetching all photos from photostream')

        _ensure_dir_exists(self.photostream_dir)

        new_files = set()

        current_page = 1

        metadata_fields = ('description,license,date_upload,date_taken,owner_name,icon_server,original_format,'
                           'last_update,geo,tags,machine_tags,o_dims,media')

        if self.include_views:
            metadata_fields += ',views'

        download_errors = []
        while True:
            rsp = self.flickr.people_getPhotos(
                user_id='me',
                extras=metadata_fields,
                per_page=NUM_PHOTOS_PER_BATCH,
                page=current_page,
            )
            _validate_json_response(rsp)

            photos = rsp['photos']['photo']
            for photo in photos:
                try:
                    new_files |= self._download_photo(photo)
                except VideoDownloadError as e:
                    download_errors.append(e)

            if rsp['photos']['pages'] == current_page:
                # We've reached the end of the photostream.  Stop looping.
                break

            current_page += 1

        # Error out if there were exceptions
        if download_errors:
            sys.stderr.write("Error: Some files failed to download:\n")
            for error in download_errors:
                sys.stderr.write("  " + str(error) + "\n")
            sys.exit(1)

        # Error out if we didn't fetch any photos
        if not new_files:
            sys.stderr.write('Error: The Flickr API returned an empty list of photos. '
                             'Bailing out without deleting any local copies in case this is an anomaly.\n')
            sys.exit(1)

        # Divide by 2 because we want to ignore the photo metadata files
        # for the purposes of our statistics.
        self.deleted_photos = self._delete_unknown_files(self.photostream_dir, new_files, 'file') / 2

    def _download_photo(self, photo):
        """Fetch and save a media item (photo or video) and the metadata
        associated with it.

        Returns a python set containing the filenames for the data.
        """
        url = None
        photo_basename = None
        mediatype = photo['media']
        if mediatype == 'photo':
            urlformat = (
                'https://farm%(farm)s.staticflickr.com/%(server)s/%(id)s_%(originalsecret)s_o.%(originalformat)s')
            url = urlformat % photo
            photo_basename = '%s.%s' % (photo['id'], photo['originalformat'])
        elif mediatype == 'video':
            # This URL gets redirected to the CDN. By looking at the CDN URL, we can find out the video's
            # original name.
            #
            # URL created according to these instructions:
            # http://code.flickr.net/2009/03/02/videos-in-the-flickr-api-part-deux/
            url = 'http://www.flickr.com/photos/%(owner)s/%(id)s/play/orig/%(originalsecret)s/' % photo
            head = requests.head(url, allow_redirects=True)

            if head.status_code is not 200:
                # For some videos the above URL doesn't work, and the only way I know how to
                # get those is to download them manually using a logged in web browser. Just
                # tell the user that. /johan.walles@gmail.com - 2016feb12
                raise VideoDownloadError('Manual download required: '
                                         'https://www.flickr.com/video_download.gne?id=%(id)s' % photo)

            photo_basename = os.path.basename(urllib.parse.urlparse(head.url).path)
        else:
            sys.stderr.write('Error: Unsupported media type "%s":\n' % mediatype)
            sys.stderr.write(json.dumps(photo, indent=2) + '\n')
            sys.exit(1)

        photo_filename = os.path.join(self.photostream_dir, photo_basename)
        metadata_basename = '%s.metadata' % photo_basename
        metadata_filename = '%s.metadata' % photo_filename

        # Sanity check
        if os.path.isdir(photo_filename) or os.path.islink(photo_filename):
            sys.stderr.write('Error: %s exists but is not a file.  This is not allowed.\n' % photo_filename)
            sys.exit(1)

        # Sanity check
        if os.path.isdir(metadata_filename) or os.path.islink(metadata_filename):
            sys.stderr.write('Error: %s exists but is not a file.  This is not allowed.\n' % metadata_filename)
            sys.exit(1)

        # Download photo if photo doesn't exist, if metadata doesn't exist or if
        # metadata has changed
        should_download_photo = not os.path.exists(photo_filename)
        should_download_photo |= not os.path.exists(metadata_filename)
        should_download_photo |= self._is_file_different(metadata_filename, photo)

        if should_download_photo:
            if not os.path.exists(photo_filename):
                self.new_photos += 1
            else:
                self.modified_photos += 1

            self._progress('Fetching %s' % photo_basename)
            request = requests.get(url, stream=True)
            if not request.ok:
                sys.stderr.write(
                    'Error: Failed to fetch %s: %s: %s'
                    % (url, request.status_code, request.reason))
                sys.exit(1)
            with open(self.tmp_filename, 'wb') as tmp_file:
                # Use 1 MiB chunks.
                for chunk in request.iter_content(2**20):
                    tmp_file.write(chunk)
            os.rename(self.tmp_filename, photo_filename)
        else:
            self._verbose('Skipping %s because we already have it'
                          % photo_basename)

        # Write metadata
        if self._write_json_if_changed(metadata_filename, photo):
            self._progress('Updated metadata for %s' % photo_basename)
        else:
            self._verbose(
                'Skipping metadata for %s because we already have it' %
                photo_basename)

        timestamp = _get_timestamp(photo)
        self._set_timestamp_if_changed(timestamp, photo_filename)
        self._set_timestamp_if_changed(timestamp, metadata_filename)

        return {photo_basename, metadata_basename}

    def _mirror_albums(self):
        """Create a directory for each album, and create symlinks to the
        files in the photostream."""
        self._verbose('Creating local albums...')

        album_dirs = set()

        # Fetch albums
        rsp = self.flickr.photosets_getList()
        _validate_json_response(rsp)
        if rsp['photosets']:
            for album in rsp['photosets']['photoset']:
                album_dirs |= self._mirror_album(album)

        self._delete_unknown_files(self.albums_dir, album_dirs, 'album')

    def _mirror_album(self, album):
        self._verbose('Creating local album %s' % album['title']['_content'])

        album_basename = self._get_album_dirname(album['id'], album['title']['_content'])
        album_dir = os.path.join(self.albums_dir, album_basename)

        # Fetch list of photos
        photoids = []
        originalformat = {}

        num_pages = int(math.ceil(float(album['photos']) / NUM_PHOTOS_PER_BATCH))
        for current_page in range(1, num_pages + 1):
            # Fetch photos in this album
            rsp = self.flickr.photosets_getPhotos(
                photoset_id=album['id'],
                extras='original_format',
                per_page=NUM_PHOTOS_PER_BATCH,
                page=current_page,
            )
            _validate_json_response(rsp)

            for photo in rsp['photoset']['photo']:
                photoids.append(photo['id'])
                originalformat[photo['id']] = photo['originalformat']

        # Include list of pictures in metadata
        album['photos'] = photoids

        if (not self.include_views) and 'count_views' in album:
            del album['count_views']

        metadata_filename = os.path.join(album_dir, 'metadata')

        # TODO: Should ensure local album directory accurately reflects the
        # remote album data even if the metadata hasn't changed (important in
        # case the local album data has been tampered with).
        if not os.path.exists(album_dir) or self._is_file_different(metadata_filename, album):
            # Metadata changed, might be due to updated list of photos.
            self._progress('Updating album %s' % album['title']['_content'])
            self.modified_albums += 1

            # Delete and recreate the album
            _ensure_dir_doesnt_exist(album_dir)
            _ensure_dir_exists(album_dir)

            # Create symlinks for each photo, prefixed with a number so that
            # the local alphanumeric sort order matches the order on Flickr.
            digits = len(str(len(photoids)))
            for i, photoid in enumerate(photoids):
                photo_basename = '%s.%s' % (photoid, originalformat[photoid])
                photo_fullname = os.path.join(self.photostream_dir, photo_basename)
                photo_relname = os.path.relpath(photo_fullname, album_dir)
                symlink_basename = '%s_%s.%s' % (str(i+1).zfill(digits), photoid, originalformat[photoid])
                symlink_filename = os.path.join(album_dir, symlink_basename)
                os.symlink(photo_relname, symlink_filename)

            # Write metadata
            self._write_json_if_changed(metadata_filename, album)

        else:
            self._verbose('Album %s is up-to-date' % album['title']['_content'])

        return {album_basename}

    def _create_not_in_any_album_dir(self):
        """Create a directory for photos that aren't in any album, and
        create symlinks to the files in the photostream."""

        self._verbose('Creating local directory for photos not in any album')

        old_album_dir = os.path.join(self.dest_dir, 'Not in any set')
        album_dir = os.path.join(self.dest_dir, 'Not in any album')

        # Rename dir from old name to new name, if applicable. This is only
        # needed to migrate people who used older versions of this script.
        # It can be removed once everyone has been migrated.
        # TODO: Remove this and the old_album_dir variable at some point. It
        # was added on 2014-12-14. Maybe remove it a year later?
        if os.path.isdir(old_album_dir):
            if os.path.exists(album_dir):
                sys.stderr.write(
                    'Error: Wanted to rename %s to %s, but the latter '
                    'already exists. Please remove one of these.\n'
                    % (old_album_dir, album_dir))
                sys.exit(1)
            os.rename(old_album_dir, album_dir)

        # TODO: Ideally we would inspect the existing directory and
        # make sure it's correct, but that's a lot of work. For now
        # just recreate the album. Fixing this would also allow us to
        # log _progress() messages when the album has changed.
        _ensure_dir_doesnt_exist(album_dir)
        _ensure_dir_exists(album_dir)

        # Fetch list of photos
        current_page = 1
        while True:
            # Fetch photos that aren't in any album
            rsp = self.flickr.photos_getNotInSet(
                extras='original_format',
                per_page=NUM_PHOTOS_PER_BATCH,
                page=current_page,
            )
            _validate_json_response(rsp)
            photos = rsp['photos']['photo']
            if not photos:
                # We've reached the end of the photostream.  Stop looping.
                break

            for photo in photos:
                photo_basename = '%s.%s' % (photo['id'], photo['originalformat'])
                photo_fullname = os.path.join(self.photostream_dir, photo_basename)
                photo_relname = os.path.relpath(photo_fullname, album_dir)
                symlink_filename = os.path.join(album_dir, photo_basename)
                os.symlink(photo_relname, symlink_filename)

            current_page += 1

    def _mirror_collections(self):
        """Create a directory for each collection, and create symlinks to the
        albums."""
        self._verbose('Creating local collections...')

        collection_dirs = set()

        # Fetch collections
        rsp = self.flickr.collections_getTree()
        _validate_json_response(rsp)
        if rsp['collections']:
            for collection in rsp['collections']['collection']:
                collection_dirs |= self._mirror_collection(collection)

        self._delete_unknown_files(self.collections_dir, collection_dirs, 'collection')

    def _mirror_collection(self, collection):
        collection_basename = self._get_collection_dirname(collection['id'], collection['title'])
        collection_dir = os.path.join(self.collections_dir, collection_basename)

        metadata_filename = os.path.join(collection_dir, 'metadata')

        if not os.path.exists(collection_dir) or self._is_file_different(metadata_filename, collection):
            # Metadata changed, might be due to updated list of albums.
            self._progress('Updating collection %s' % collection['title'])
            self.modified_collections += 1

            # Delete and recreate the collection
            _ensure_dir_doesnt_exist(collection_dir)
            _ensure_dir_exists(collection_dir)

            # Create symlinks for each album
            for album in collection['set']:
                album_basename = self._get_album_dirname(album['id'], album['title'])
                album_fullname = os.path.join(self.albums_dir, album_basename)
                album_relname = os.path.relpath(album_fullname, collection_dir)
                symlink_filename = os.path.join(collection_dir, album_basename)
                os.symlink(album_relname, symlink_filename)

            # Write metadata
            self._write_json_if_changed(metadata_filename, collection)

        return {collection_basename}

    @staticmethod
    def _get_album_dirname(id_, title):
        safe_title = urllib.parse.quote(title.encode('utf-8'), " ',")
        # TODO: We use the ID in the name to avoid conflicts when there are
        #       two albums with the same name.  Is there a better way to
        #       handle that?  Maybe by using the date of the oldest picture
        #       instead?
        return '%s - %s' % (safe_title, id_)

    @staticmethod
    def _get_collection_dirname(id_, title):
        safe_title = urllib.parse.quote(title.encode('utf-8'), " ',")
        # TODO: We use the ID in the name to avoid conflicts when there are
        #       two collections with the same name (is that even possible?)
        #       Is there a better way to handle that?
        return '%s - %s' % (safe_title, id_)

    @staticmethod
    def _is_file_different(filename, data):
        """Return True if the contents of the file 'filename' differ
        from 'data'. Otherwise return False."""
        try:
            with open(filename) as json_file:
                orig_data = json.load(json_file)
            return orig_data != data
        except IOError as ex:
            if ex.errno != errno.ENOENT:
                sys.stderr.write('Error reading %s: %s\n' % (filename, ex))
                sys.exit(1)
            return True

    def _set_timestamp_if_changed(self, timestamp, file):
        stat0 = os.stat(file)
        timestamp_since_epoch = time.mktime(timestamp.timetuple())
        os.utime(file, (timestamp_since_epoch, timestamp_since_epoch))

        stat1 = os.stat(file)
        if stat0.st_mtime != stat1.st_mtime:
            self._verbose("%s: Re-timestamped to %s" % (os.path.basename(file), timestamp))

    def _write_json_if_changed(self, filename, data):
        """Write the given data to the specified filename, but only if it's
        different from what is currently there. Return true if the file was
        written.

        We use this function mostly to avoid changing the timestamps on
        metadata files."""
        if not self._is_file_different(filename, data):
            # Data has not changed--do nothing.
            return False

        with open(self.tmp_filename, 'w') as json_file:
            json.dump(data, json_file)
        os.rename(self.tmp_filename, filename)
        return True

    def _delete_unknown_files(self, rootdir, known, knowntype):
        """Delete all files and directories in rootdir except the
        known files.  knowntype if only used for the log message.
        Returns the number of deleted entries."""
        delete_count = 0
        curr_entries = os.listdir(rootdir)

        unknown_entries = set(curr_entries) - set(known)
        for unknown_entry in unknown_entries:
            fullname = os.path.join(rootdir, unknown_entry)
            self._progress('Deleting unknown %s: %s' % (knowntype, unknown_entry))
            delete_count += 1

            try:
                if os.path.isdir(fullname):
                    shutil.rmtree(fullname)
                else:
                    os.remove(fullname)
            except OSError as ex:
                sys.stderr.write('Error deleting %s: %s\n' % (fullname, ex.strerror))
                sys.exit(1)

        return delete_count

    def _verbose(self, msg):
        if self.verbosity >= 2:
            print(msg)

    def _progress(self, msg):
        if self.verbosity >= 1:
            print(msg)

    def _cleanup(self):
        # Remove a temp file, if one exists
        try:
            os.remove(self.tmp_filename)
        except OSError as ex:
            if ex.errno != errno.ENOENT:
                sys.stderr.write('Error deleting temp file %s: %s\n' % (self.tmp_filename, ex.strerror))


def main():
    _check_flickrapi_version()

    parser = argparse.ArgumentParser(
        description='Create a local mirror of your flickr data.')

    parser.add_argument(
        'destdir',
        help='the path to where the mirror shall be stored')

    parser.add_argument(
        '-v', '--verbose',
        dest='verbosity', action='store_const', const=2,
        default=1,
        help='print progress information to stdout')

    parser.add_argument(
        '-q', '--quiet',
        dest='verbosity', action='store_const', const=0,
        help='print nothing to stdout if the mirror succeeds')

    parser.add_argument(
        '-s', '--statistics', action='store_const',
        default=False, const=True,
        help='print transfer-statistics at the end')

    parser.add_argument(
        '--ignore-views', action='store_const',
        dest='include_views', default=True, const=False,
        help='do not include views-counter in metadata')

    args = parser.parse_args()

    mirrorer = FlickrMirrorer(args.destdir, args.verbosity,
                              args.statistics, args.include_views)
    mirrorer.run()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # User exited with CTRL+C
        # Print a newline to leave the console in a prettier state
        print