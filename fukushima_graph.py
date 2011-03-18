#!/usr/bin/env python
# -*- coding: utf8 -*-

import os.path
import re
import subprocess
import sys
import time
import urllib2


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


def get_latest_pdf(url):
    pdf = urllib2.urlopen(url).read()
    f = open(LATEST_PDF, 'wb')
    f.write(pdf)
    f.close()
    p = subprocess.Popen(['pdftotext', LATEST_PDF, LATEST_TXT])
    p.communicate()


def update_data():
    f = open(LATEST_TXT, 'r')
    raw = unicode(f.read(), 'utf-8')
    f.close()

    data_start = re.search(u'(?P<mon>\\d{1,2})月(?P<day>\\d{1,2})日\s+\\d{1,2}:\\d{1,2}',
            raw, re.U | re.S)
    data_break = re.search(u'（\\w）', raw, re.U)
    data_end = re.search(u'測定装置', raw, re.U)

    # First group includes start to get the time, 2nd for ease of coding
    rows = (raw[data_start.start():data_break.start()],
            raw[data_break.start():data_end.start()])

    data = []
    f = open('fukushima.dat', 'r')
    lines = f.readlines()
    if lines:
        last_time = lines[-1].split('\t')[0]
    else:
        last_time = ''
    f.close()
    f = open('fukushima.dat', 'a')
    for r in rows:
        cells = r.strip().split('\n\n')
        ts = cells[1].split(':')
        ts_str = '2011/%s/%s-%s:%s' % (data_start.group('mon'),
            data_start.group('day'), ts[0], ts[1])
        if ts_str > last_time:
            data_str = ''
            for c in cells[2:]:
                if c.strip() == u'ー':
                    data_str += '-\t'
                    continue
                try:
                    float(c.strip())
                except ValueError:
                    data_str += '-\t'
                    continue
                data_str += c.strip() + '\t'
            f.write('%s\t%s\n' % (ts_str, data_str[:-1]))
    f.close()


def plot_data(places, dest_dir):
    p = subprocess.Popen(['gnuplot', '-p'], shell=True, stdin=subprocess.PIPE)
    p.stdin.write('set terminal png size 1024,768\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'fukushima_levels.png',)))
    p.stdin.write('set xlabel "Time (Day Hour:Minute)"\n')
    p.stdin.write('set timefmt "%Y/%m/%d-%H:%M"\n')
    p.stdin.write('set xdata time\n')
    p.stdin.write('set xrange ["2011/03/18-06:00":]\n')
    p.stdin.write('set format x "%d %H:%M"\n')
    p.stdin.write('set xtics 43200\n')
    p.stdin.write('set ylabel "Microsievert/hour"\n')
    p.stdin.write('set title "Radiation levels in Fukushima Prefecture (Updated '
            'at %s)"\n' % (time.strftime('%Y/%m/%d %H:%M ' + time.tzname[0],
                time.localtime()),))
    plot_cmd = 'plot '
    for ii, place in enumerate(places):
        plot_cmd += '"fukushima.dat" u 1:%d title "%s" w l, ' % (ii + 2, place)
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
    dest_dir = '/home/killbots/killbots.net/random'
    if len(argv) > 1:
        dest_dir = argv[1]

    latest_url = get_latest_update()
    previous_url = get_previous_url()

    if latest_url != previous_url:
        get_latest_pdf(latest_url)
        write_previous_url(latest_url)
    update_data()

    places = ['Fukushima City', 'Koriyama City', 'Shirakawa City',
            'Aizu-Wakamatsu', 'Aizu Town South', 'Soma City South',
            'Iwaki City', 'Tamagawa', 'Iitate', 'Kawauchi',
            'Central Iwaki City', 'Tamura City Funehiki', 'Tamura City Tokiwa']
    plot_data(tuple(places), dest_dir)


if __name__ == '__main__':
    main(sys.argv)

