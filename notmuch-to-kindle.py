#!/usr/bin/python2.6
# -*- coding: utf-8 -*-
#
# Written by Albin Stjerna and placed in the Public Domain. Use any
# way you like, don't complain if it breaks. Or do, and suggest
# improvements.

import ConfigParser, subprocess, notmuch, os, tempfile, base64, datetime, re, shutil, mimetypes, string
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
types_to_convert = ['text/html']
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


# def get_html_multipart(mail):
#     "Return the text/html part of a multipart mail, or simply the first part if not multipart"
            
#     if not mail.is_multipart():
#         return mail.get_payload(decode=True)
#     else:
#         for part in mail.walk():
# #            if part.get_content_maintype() == 'application':
#  #               print part.get_content_type()

#             # iterate over entire mail. if there's a text/html and a text/plain, prefer html.
#             # if there's an application/pdf, extract it.
#             # ext = mimetypes.guess_extension(part.get_content_type()) (see http://docs.python.org/library/email-examples.html)

#             # don't bother with multipart, they're just containers
#             if part.get_content_maintype() == 'multipart':
#                 continue
#             else:
#                 print part.get_content_type()

#         payloads = mail.get_payload()
#         for load in payloads:
#             if load.get_content_type() == "text/html":
#                 return load.get_payload(decode=True)
#             elif load.is_multipart():
#                 return get_html_multipart(load)
#         # if we got here we're screwed


tempfolder = tempfile.mkdtemp()

def gen_item (mail):
    with open(mail.get_filename(), 'r') as fp:
        mailfile = Parser().parse(fp)
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
            ext = mimetypes.guess_extension(part.get_content_type())
            if not ext:
                # Use a generic bag-of-bits extension
                ext = '.bin'
            filename = '%s-part-%03d%s' % (mail.get_header("Subject"), counter, ext)
        filename = sanitize_filename(filename)
        print filename
        counter += 1
        with open(os.path.join(tempfolder, filename), 'wb') as fp:
            fp.write(part.get_payload(decode=True))
            fp.close()
        if part.get_content_type() in types_to_convert:
            # html files needs conversion.
            p = subprocess.Popen(
                ['ebook-convert',
                 os.path.join(tempfolder, filename), 
                 os.path.join(tempfolder, os.path.splitext(filename)[0] + ".mobi"),
                 '--input-profile=%s' % config.get("ebook-convert", "input_profile"),
                 '--authors="%s"'  % mail.get_header("From"),
                 '--pubdate="%d"'  % mail.get_date(),
                 '--title="%s"'    % mail.get_header("Subject"),
                 '--comments="%s"' % url], 
                stdout=subprocess.PIPE, stderr = subprocess.PIPE)
            stdout, stderr = p.communicate()


map(gen_item, maillist)

for f in filter(lambda x: (x.endswith(".mobi") or x.endswith(".pdf")), os.listdir(tempfolder)):
    path = "%s/%s" % (tempfolder, f)
    print "now copying " + path + " to " + config.get("main", "target")
    shutil.copy(path, config.get("main", "target"))

shutil.rmtree(tempfolder)
