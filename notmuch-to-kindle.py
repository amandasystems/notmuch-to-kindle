#!/usr/bin/python2.6
# -*- coding: utf-8 -*-
#
# Written by Albin Stjerna and placed in the Public Domain. Use any
# way you like, don't complain if it breaks. Or do, and suggest
# improvements.

import ConfigParser, subprocess, notmuch, os, tempfile, base64, datetime, re, shutil
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

iterator = 0
for m in mails:
    if iterator < max_entries:
        maillist.append(m)
        iterator +=1
    else:
        break


def get_html_multipart(mail):
    "Return the text/html part of a multipart mail, or simply the first part if not multipart"
    if not mail.is_multipart():
        return mail.get_payload()
    else:
        payload = mail.get_payload()
        for load in payload:
            if load.get_content_type() == "text/html":
                return load.get_payload()
            elif load.is_multipart():
                return get_html_multipart(load)
        # if we got here we're screwed

tempfolder = tempfile.mkdtemp()

def gen_item (mail):
    fp = open(mail.get_filename(), 'r')
    mailfile = Parser().parse(fp)
    url = find_url_in_mail(mailfile)
    
    content = get_html_multipart(mailfile)
    if content == None:
        if not mailfile.get_payload()[0] == None:            
            content = mailfile.get_payload()[0].as_string()
        else:
            print "Warning! No content in email %s!" % mail.get_message_id()
            return

    fp.close()

    base_filename="%s/%s" % (tempfolder, base64.urlsafe_b64encode(mail.get_message_id()))
    f = open(base_filename + ".html", 'w')
    f.write(content)
    f.close()

    p = subprocess.Popen(
        ['ebook-convert',
         base_filename + ".html", 
         base_filename + ".mobi",
         '--input-profile=%s' % config.get("ebook-convert", "input_profile"),
         '--authors="%s"'  % mail.get_header("From"),
         '--pubdate="%d"'  % mail.get_date(),
         '--title="%s"'    % mail.get_header("Subject"),
         '--comments="%s"' % url], 
        stdout=subprocess.PIPE, stderr = subprocess.PIPE)
    stdout, stderr = p.communicate()
    return


map(gen_item, maillist)

for f in filter(lambda x: x.endswith(".mobi"), os.listdir(tempfolder)):
    path = "%s/%s" % (tempfolder, f)
    print "now copying " + path + " to " + config.get("main", "target")
    shutil.copy(path, config.get("main", "target"))

shutil.rmtree(tempfolder)
