#!/usr/bin/env python

import locale
import os
import sys
import json
import datetime
import difflib
from dropbox import client, rest, session

FOLDER_YESDEFY = '/YesDefy'
FOLDER_NEW = FOLDER_YESDEFY + '/new'
FILE_FILELIST = 'filelist.txt'
FILE_FILELIST_LAST = 'filelist_last.txt'
FILE_NEWFILES = 'newfiles.txt'

HEADER_FILELIST_UPDATED = '# last updated at:'
HEADER_TO_FILE = '+++'
HEADER_NEWFILES_UPDATED = '# new files found at:'
HEADER_SEPARATOR = '##############################################################################'
EXT_TORRENT = '.torrent'

class MyDropbox():
    new_files = []
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
            pass
        pass

    def db_find(self, folder="/"):
        if self.api_client is None:
            exit()
        client = self.api_client
        allfiles = {}
        cursor=None
        has_more = True
        while has_more:
            result = client.delta(cursor)
            cursor = result['cursor']
            has_more = result['has_more']

        for lowercase_path, metadata in result['entries']:
            if metadata is not None:
                allfiles[lowercase_path] = metadata
            else:
                # remove it if there is no metadata that indicates a deletion.
                allfiles.pop(lowercase_path, None)

        files = []
        for f in allfiles.keys():
            if not allfiles[f]['is_dir']:
                filename = allfiles[f]['path']
                if filename.startswith(FOLDER_YESDEFY):
                    files.append(filename)
        files.sort()
        return files

    def db_put(self, from_path, to_path):
        with open(os.path.expanduser(from_path), 'rb') as from_file:
            encoding = locale.getdefaultlocale()[1] or 'ascii'
            full_path = to_path.decode(encoding)
            self.api_client.put_file(full_path, from_file, True)
        pass

    def db_get(self, from_path, to_path):
        with open(os.path.expanduser(to_path), "wb") as to_file:
            try:
                f, metadata = self.api_client.get_file_and_metadata(from_path)
                to_file.write(f.read())
            except rest.ErrorResponse as e:
                print '(%d)[%s] %s (%s)' % (e.status, e.reason, e.error_msg, from_path)
                to_file.write('')
        pass

    def db_copy(self, from_path, to_path):
        self.api_client.file_copy(from_path, to_path)
        pass

    def check_new_files(self , from_file, to_file):
        self.new_files = []
        with open(FILE_FILELIST, 'r') as filelist:
            with open(FILE_FILELIST_LAST, 'r') as filelist_last:
                diff = difflib.unified_diff(
                    filelist_last.readlines(),
                    filelist.readlines(),
                    fromfile='filelist_last',
                    tofile='filelist',
                )
                for line in diff:
                     line = line.strip('\n\r')
                     if line.startswith('+'):
                         if line.startswith(HEADER_TO_FILE):
                             continue
                         elif line[1:].startswith(HEADER_FILELIST_UPDATED):
                             continue
                         elif not line[1:].startswith(FOLDER_YESDEFY):
                             continue
                         elif line[1:].startswith(FOLDER_NEW):
                             continue
                         else:
                            self.new_files.append(line[1:])
                     pass
                pass
            pass
        pass
        return self.new_files

    def write_file(self, filename, data):
        with open(filename, 'w') as f:
            for d in data:
                f.write(d.encode('utf8')+'\r\n')
        pass

    def write_filelist(self, filename, data):
        filelist_log = []
        filelist_log.append(('%s %s' % (HEADER_FILELIST_UPDATED, str(datetime.datetime.now()))))
        filelist_log.append('')
        filelist_log.extend(data)
        self.write_file(filename, filelist_log)
        pass

    def copy_new_torrents_to_folder(self, new_files, to_folder):
        new_files_logs = []
        new_files_logs.append(HEADER_SEPARATOR)
        new_files_logs.append('%s %s' % (HEADER_NEWFILES_UPDATED, str(datetime.datetime.now())))
        for new_file in new_files:
            new_files_logs.append(new_file)
            if new_file.endswith(EXT_TORRENT):
                head, tail = os.path.split(new_file)
                filename = tail
                try:
                    self.db_copy(new_file, to_folder + '/' + filename)
                except rest.ErrorResponse as e:
                    new_files_logs.append('(%d)[%s] %s' % (e.status, e.reason, e.error_msg))
                pass
            pass

        last_content = None
        with open(FILE_NEWFILES, 'r+') as f:
            last_content = f.read()

        new_files_logs.append('')
        new_files_logs.append(last_content)
        self.write_file(FILE_NEWFILES, new_files_logs)
        pass

    def is_new_files(self):
        return True if len(self.new_files) is not 0 else False

def show_usage():
    print "usage:"
    print "  python " + os.path.basename(__file__) + " {tokens.json}"
    pass

def main():
    if len(sys.argv) < 2:
        show_usage()
        exit()
    tokens = sys.argv[1]
    myDropbox = MyDropbox(tokens)
    myDropbox.db_get(FOLDER_YESDEFY + '/' + FILE_FILELIST, FILE_FILELIST_LAST)
    myDropbox.db_get(FOLDER_NEW + '/' + FILE_NEWFILES, FILE_NEWFILES)
    files = myDropbox.db_find()
    myDropbox.write_filelist(FILE_FILELIST, files)

    new_files = myDropbox.check_new_files(FILE_FILELIST_LAST, FILE_FILELIST)
    if myDropbox.is_new_files():
        myDropbox.copy_new_torrents_to_folder(new_files, FOLDER_NEW)
        myDropbox.db_put(FILE_FILELIST, FOLDER_YESDEFY + '/' + FILE_FILELIST)
        myDropbox.db_put(FILE_NEWFILES, FOLDER_NEW + '/' + FILE_NEWFILES)
        pass
    pass

if __name__ == '__main__':
    main()
    pass
