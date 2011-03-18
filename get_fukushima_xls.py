#!/usr/bin/env python
# -*- coding: utf8 -*-

import os.path
import re
import sys
import time
import urllib2


def get_latest_update():
    url = 'http://www.pref.fukushima.jp/j/index.htm'
    html = urllib2.urlopen(url).read()
    m = re.search(r'(http://www.pref.fukushima.jp/j/sokuteichi\d+.xls)',
            html, re.U | re.S)
    if not m:
        m = re.search(r'(http://www.pref.fukushima.jp/j/sokuteichi\d+.pdf)',
                html, re.U | re.S)
    return m.group(1)


def get_previous_url():
    try:
        f = open('fukushima_url.cache', 'r')
    except IOError:
        return ''
    url = f.read()
    f.close()
    return url


def write_previous_url(url):
    f = open('fukushima_url.cache', 'w')
    f.write(url)
    f.close()


def main(argv):
    dest_dir = '/home/killbots/killbots.net/random/fukushima'
    if (len(argv) > 1):
        dest_dir = argv[1]

    latest_url = get_latest_update()
    previous_url = get_previous_url()

    if latest_url != previous_url:
        ext = os.path.splitext(latest_url)[1]
        data = urllib2.urlopen(latest_url).read()
        dest = 'fukushima_%s' % (time.strftime('%d_%H:%M_' + time.tzname[0],
            time.localtime()),) + ext
        f = open(os.path.join(dest_dir, dest), 'wb')
        f.write(xls)
        f.close()
        write_previous_url(latest_url)


if __name__ == '__main__':
    main(sys.argv)

