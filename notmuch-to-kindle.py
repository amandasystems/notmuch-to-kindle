#!/usr/bin/python2.6
# -*- coding: utf-8 -*-
#
# Written by Albin Stjerna and placed in the Public Domain. Use any
# way you like, don't complain if it breaks. Or do, and suggest
# improvements.

import ConfigParser, subprocess, notmuch, os, tempfile, datetime, shutil, mimetypes, string, sys
from email.parser import Parser

def find_url_in_mail(mail):
    "try finding an URL in a sluk header, fall back to using regular expressions"
    url = mail.get("X-Entry-URL")
    return url

config = ConfigParser.ConfigParser()
conf_file = os.path.expanduser('~/.notmuch-to-kindlerc')

if os.path.exists(conf_file):
    config.readfp(open(conf_file))

db = notmuch.Database()
nm_query = notmuch.Query(db, 'tag:' + config.get("main", "tag"))
nm_query.set_sort(notmuch.Query.SORT.NEWEST_FIRST)
mails = nm_query.search_messages()

maillist = []

max_entries = config.getint("main", "max")
types_to_convert = ['text/html', 'application/epub+zip']
iterator = 0
for m in mails:
    if iterator < max_entries:
        maillist.append(m)
        iterator +=1
    else:
        break

def sanitize_filename(fn):
    valid_chars = frozenset("-_.() %s%s" % (string.ascii_letters, string.digits))
    return ''.join(c for c in fn if c in valid_chars)

def calibre_to_mobi(path, filename, authors, date, title, url):
    p = subprocess.Popen(
        ['ebook-convert',
         os.path.join(path, filename), 
         os.path.join(path, os.path.splitext(filename)[0] + ".mobi"),
         '--input-profile=%s' % config.get("ebook-convert", "input_profile"),
         '--authors="%s"'  % authors, 
         '--pubdate="%d"'  % date, 
         '--title="%s"'    % title, 
         '--comments="%s"' % url], 
        stdout=subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = p.communicate()
    

tempfolder = tempfile.mkdtemp()

def gen_item (mail):
    with open(mail.get_filename(), 'r') as fp:
        mailfile = Parser().parse(fp)
        fp.close()
    url = find_url_in_mail(mailfile)    
    counter = 1

    for part in mailfile.walk():
        # multipart/* are just containers
        if part.get_content_maintype() == 'multipart':
            continue
        # Applications should really sanitize the given filename so that an
        # email message can't be used to overwrite important files
        filename = part.get_filename()
        if not filename:
            if part.get_content_type() == 'text/plain':
                ext = '.txt'
            else: 
                ext = mimetypes.guess_extension(part.get_content_type())
            if not ext:
                # Use a generic bag-of-bits extension
                ext = '.bin'
            filename = '%s-part-%03d%s' % (mail.get_header("Subject"), counter, ext)
        filename = sanitize_filename(filename)
        counter += 1
        with open(os.path.join(tempfolder, filename), 'wb') as fp:
            payload = part.get_payload(decode=True)
            if not payload == None:
                fp.write(part.get_payload(decode=True))
                fp.close()
            else:
                print >> sys.stderr, "Error: Unable to extract payload from filename %s, part dump following:" % filename
                print >> sys.stderr, part
                print >> sys.stderr, "End of part dump for file named %s." % filename
        basename, ext = os.path.splitext(filename)
        if ext == '.doc':
            # process with abiword!
            try:
                p = subprocess.Popen(['abiword',
                                      '--to=%s.html' % os.path.join(tempfolder, basename),
                                      os.path.join(tempfolder, filename)],
                                     stdout=subprocess.PIPE, stderr = subprocess.PIPE)
                stdout, stderr = p.communicate()
            except OSError, e:
                print >>sys.stderr, "Failed to convert to html using abiword. Possibly missing abiword? Got error: ", e
            # TODO implement optional arguments in calibre_to_mobi
            calibre_to_mobi(tempfolder, basename + '.html', "", 0, "", "")
        if part.get_content_type() in types_to_convert:
            # html files needs conversion.
            calibre_to_mobi(tempfolder, filename, mail.get_header("From"), 
                            mail.get_date(), mail.get_header("Subject"), url)

map(gen_item, maillist)

try:
    for f in filter(lambda x: (os.path.splitext(x)[1] in [".pdf", ".mobi", ".azw", ".txt"]), os.listdir(tempfolder)):
        path = "%s/%s" % (tempfolder, f)
#        print "now copying " + path + " to " + config.get("main", "target")
        shutil.copy(path, config.get("main", "target"))
finally:
 #   print "removed temporary files"
    shutil.rmtree(tempfolder)
