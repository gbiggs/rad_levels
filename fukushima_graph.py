#!/usr/bin/env python
# -*- coding: utf8 -*-

import datetime
import os.path
import re
import subprocess
import sys
import time
import urllib2

import cache


CACHE='fukushima.dat'
LATEST_PDF='fukushima_latest.pdf'
LATEST_TXT='fukushima_latest.txt'


def get_latest_update():
    url = 'http://www.pref.fukushima.jp/j/index.htm'
    html = urllib2.urlopen(url).read()
    data_url = re.search(r'(http://www.pref.fukushima.jp/j/sokuteichi\d+.pdf)',
            html, re.U | re.S).group(1)
    return data_url


def get_previous_url():
    try:
        f = open('fukushima_graph_url.cache', 'r')
    except IOError:
        return ''
    url = f.read()
    f.close()
    return url


def write_previous_url(url):
    f = open('fukushima_graph_url.cache', 'w')
    f.write(url)
    f.close()


def get_latest_pdf(url):
    pdf = urllib2.urlopen(url).read()
    f = open(LATEST_PDF, 'wb')
    f.write(pdf)
    f.close()
    p = subprocess.Popen(['pdftotext', '-layout', '-raw', LATEST_PDF, LATEST_TXT])
    p.communicate()


def update_data():
    f = open(LATEST_TXT, 'r')
    raw = unicode(f.read(), 'utf-8')
    f.close()

    start_line = re.search(r'\d{3}\s\d{1,2}:\d{1,2}', raw)
    end_line = re.search(r'\d+km', raw[start_line.end():])

    raw = raw[start_line.end():end_line.start() + start_line.end()]

    date = re.search(r'^(?P<mon>\d)(?P<day>\d{1,2})', raw, re.M)
    ts = re.search(r'^\s?(?P<hour>\d{1,2}):(?P<min>\d{2})', raw, re.M)
    raw = raw[ts.end():].strip()

    data = cache.load_cache(CACHE)
    ts = datetime.datetime(2011, int(date.group('mon')),
            int(date.group('day')), int(ts.group('hour')),
            int(ts.group('min')))
    cells = [m[0] for m in re.findall(r'((\d{1,2}.\d{1,2})|-)? ?', raw)]
    if len(cells) > 12:
        # Hack because we can't use a variable-length lookbehind asssertion
        # in the regex, so we almost always get an empty extra cell
        cells = cells[:12]
    while len(cells) < 12:
        cells.append('')
    for ii, c in enumerate(cells):
        if c.strip() == '':
            continue
        try:
            float(c.strip())
        except ValueError:
            continue
        data.set_value(ts, ii, c.strip())
    cache.save_cache(data, CACHE)


def plot_data(places, dest_dir):
    p = subprocess.Popen(['gnuplot', '-p'], shell=True, stdin=subprocess.PIPE)
    p.stdin.write('set terminal png size 1024,768\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'fukushima_levels.png',)))
    p.stdin.write('set xlabel "Month/Day"\n')
    p.stdin.write('set timefmt "%Y/%m/%d-%H:%M"\n')
    p.stdin.write('set xdata time\n')
    p.stdin.write('set xrange ["2011/03/15-21:00":]\n')
    p.stdin.write('set format x "%m/%d"\n')
    p.stdin.write('set xtics 86400\n')
    p.stdin.write('set ylabel "Microsievert/hour"\n')
    p.stdin.write('set title "Radiation levels in Fukushima Prefecture (Updated '
            'at %s)"\n' % (time.strftime('%Y/%m/%d %H:%M ' + time.tzname[0],
                time.localtime()),))
    plot_cmd = 'plot '
    for ii, place in enumerate(places):
        plot_cmd += '"%s" u 1:%d title "%s" w l, ' % (CACHE, ii + 2, place)
    plot_cmd = plot_cmd[:-2] + '\n'
    p.stdin.write(plot_cmd)
    p.stdin.write('set logscale y\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'fukushima_levels_log.png',)))
    p.stdin.write(plot_cmd)
    p.stdin.write('set terminal png size 640,480\n')
    p.stdin.write('set nologscale y\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'fukushima_levels_small.png',)))
    p.stdin.write(plot_cmd)
    p.stdin.write('set logscale y\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'fukushima_levels_log_small.png',)))
    p.stdin.write(plot_cmd)
    p.stdin.write('quit\n')


def main(argv):
    global CACHE
    dest_dir = '/home/killbots/killbots.net/random'
    if len(argv) > 1:
        dest_dir = argv[1]
    CACHE = os.path.join(dest_dir, CACHE)

    latest_url = get_latest_update()
    previous_url = get_previous_url()
    if latest_url != previous_url:
        get_latest_pdf(latest_url)
        #write_previous_url(latest_url)
        update_data()

    places = ['Fukushima City', 'Koriyama City', 'Shirakawa City',
            'Aizu-Wakamatsu', 'Minami Aizu', 'Minami Soma City',
            'Iwaki City', 'Tamagawa', 'Iitate', 'Kawauchi',
            'Central Iwaki City', 'Tamura City Funehiki', 'Tamura City Tokiwa']
    plot_data(tuple(places), dest_dir)


if __name__ == '__main__':
    main(sys.argv)

