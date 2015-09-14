#!/usr/bin/env python

import locale
import os
import sys
import json
import datetime
from dropbox import client, rest, session

FILE_LIST = 'filelist.txt'
FOLDER_YESDEFY = '/YesDefy'

class MyDropbox():
    def __init__(self, token_file):
        self.api_client = None
        try:
            with open(token_file) as data_file:
                data = json.load(data_file)
            app_key = data['app_key']
            app_secret = data['app_secret']
            if 'oauth1' in data:
                access_key, access_secret = data['oauth1'].split(':', 1)
                sess = session.DropboxSession(app_key, app_secret)
                sess.set_token(access_key, access_secret)
                self.api_client = client.DropboxClient(sess)
                print "[loaded OAuth 1 access token]"
            elif 'oauth2' in data:
                self.api_client = client.DropboxClient(data['oauth2'])
                print "[loaded OAuth 2 access token]"
            else:
                print "Malformed access token in %r." % (self.token_file,)
        except IOError:
            pass # don't worry if it's not there

    def do_find(self, folder="/"):
        if self.api_client is None:
            exit()
        client = self.api_client
        files = {}
        cursor=None
        has_more = True
        while has_more:
            result = client.delta(cursor)
            cursor = result['cursor']
            has_more = result['has_more']

        for lowercase_path, metadata in result['entries']:
            if metadata is not None:
                files[lowercase_path] = metadata
            else:
                # no metadata indicates a deletion
                # remove if present
                files.pop(lowercase_path, None)

        # in case this was a directory, delete everything under it
        for other in files.keys():
            if other.startswith(lowercase_path + '/'):
                del files[other]

        paths = []
        for path in files.keys():
            if not files[path]['is_dir']:
                paths.append(files[path]['path'])
        paths.sort()
        return paths

    def do_write_file(self, filename, data):
        f = open(filename, 'w')
        f.write('# last updated at: ' + str(datetime.datetime.now()) + '\r\n')
        f.write('\r\n')
        for d in data:
            f.write(d.encode('utf8')+'\r\n')
        f.close()

    def do_put(self, from_path, to_path):
        from_file = open(os.path.expanduser(from_path), 'rb')
        encoding = locale.getdefaultlocale()[1] or 'ascii'
        full_path = to_path.decode(encoding)
        self.api_client.put_file(full_path, from_file, True)

def show_usage():
    print "usage:"
    print "  python " + os.path.basename(__file__) + " {tokens.json}"

def main():
    if len(sys.argv) < 2:
        show_usage()
        exit()
    tokens = sys.argv[1]
    myDropbox = MyDropbox(tokens)
    paths = myDropbox.do_find()
    myDropbox.do_write_file(FILE_LIST, paths)
    myDropbox.do_put(FILE_LIST, FOLDER_YESDEFY + '/' + FILE_LIST)

if __name__ == '__main__':
    main()
