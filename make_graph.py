#!/usr/bin/env python
# -*- coding: utf8 -*-

import os.path
import re
import subprocess
import sys
import time
import urllib2


def process_cells(cells, dest, current_day):
    # Time stamp
    if cells[0] == u'〜':
        # No data
        return
    # Get a day/time match
    m = re.match(u'((?P<day>\\d{1,2})日\s?)?(?P<hour>\\d{1,2}):(?P<min>\\d{1,2})',
            cells[0], re.U)
    if m.group('day'):
        current_day = int(m.group('day'))
    day = current_day
    dest[0].append('2011/03/%02d-%02d:%02d' % (day, int(m.group('hour')), int(m.group('min'))))
    for ii, c in enumerate(cells[1:]):
        try:
            val = float(c)
        except ValueError:
            # No data
            dest[ii + 1].append('')
            continue
        dest[ii + 1].append(c)
    return current_day


def get_latest_update():
    url = 'http://www.pref.ibaraki.jp/important/20110311eq/index.html'
    url_finder = u'href="(?P<url>\\d{8}_\\d{2}/index.html)">茨城県の放射線量の状況　(?P<month>\\d)月(?P<day>\\d{2})日?　(?P<hour>\\d{1,2})時(?P<min>\\d{1,2})分'
    html = unicode(urllib2.urlopen(url).read(), 'shift-jis')
    m = re.search(url_finder, html, re.U)
    return m.groups()


def get_levels(url_suffix):
    levels = []
    num_places = 0
    current_day = None
    url = 'http://www.pref.ibaraki.jp/important/20110311eq/' + url_suffix
    html = unicode(urllib2.urlopen(url).read(), 'shift-jis')
    # Get the tables dealing with Ibaraki
    tables = re.findall(u'<table.*?>(?P<tables>.*?)</table>',
            html, re.U | re.S)
    for t in tables:
        rows = re.findall(u'<tr>(.*?)</tr>', t, re.U | re.S)
        # Grab the place names
        places = re.findall(u'<th.*?>.*?（(\w+?)）.*?</th>', rows[0],
                re.U | re.S)
        if num_places == 0:
            # Only need to do this once
            num_places = len(places) / 2
            levels = [[] for ii in range(num_places + 1)] # +1 for timestamp
        places = places[:num_places]

        # The rows may break in the middle, just for that extra dash of
        # excitement.

        l_cells = []
        r_cells = []
        page_break = False
        for r in rows[1:]:
            if page_break:
                page_break = False
                continue
            cells = re.findall(u'<td class.*?>(.*?)<', r, re.U | re.S)
            if not cells:
                # This is a page break in the middle of a table, just to make
                # life difficult
                for cells in l_cells + r_cells:
                    # Process the cells into timestamps and numbers
                    current_day = process_cells(cells, levels, current_day)
                l_cells = []
                r_cells = []
                page_break = True
                continue
            l_cells.append(cells[:num_places + 1])
            r_cells.append(cells[num_places + 1:])
        for cells in l_cells + r_cells:
            # Process the cells into timestamps and numbers
            current_day = process_cells(cells, levels, current_day)
    return places, levels


def get_kek():
    url = 'http://rcwww.kek.jp/norm/dose.html'
    html = urllib2.urlopen(url).read()
    value = re.search(r'<b>\s*([\d.]+)', html).group(1)
    time = re.search(r'\((?P<mon>\d{1,2})/(?P<day>\d{1,2}) '
            '(?P<hour>\d{1,2}):(?P<min>\d{1,2})', html)
    f = open('kek.dat', 'a')
    f.write('2011/%02d/%02d-%02d:%02d\t%s\n' % (int(time.group('mon')),
        int(time.group('day')), int(time.group('hour')),
        int(time.group('min')), value))
    f.close()

    f = open('kek.dat', 'r')
    times = []
    data = []
    for l in f:
        l = l.strip().split('\t')
        if len(l) == 2:
            times.append(l[0])
            data.append(l[1])
    f.close()
    return times, data


def get_aist():
    url = 'http://www.aist.go.jp/taisaku/ja/measurement/all_results.html'
    try:
        html = urllib2.urlopen(url).read()
    except urllib2.HTMLError, e:
        print >>sys.stderr, 'Error reading AIST data:', e
        return None
    except httplib.BadStatusLine:
        print >>sys.stderr, 'Error reading AIST data: bad status line'
        return None
    table = unicode(re.search(u'<table class="ment".*?>(.*?)</table>', html,
            re.U | re.S).group(1), 'shift-jis')
    rows = re.findall(u'<tr>(.*?)</tr>', table, re.U | re.S)
    times = []
    data = []
    current_day = None
    # Skip the header row
    for r in rows[1:]:
        cells = re.findall(u'<td.*?>(.*?)</td>', r, re.U | re.S)
        offset = 0
        if len(cells) == 3:
            # Got a new day
            m = re.match(u'(?P<mon>\d{1,2})月(?P<day>\d{1,2})日', cells[0],
                    re.U | re.S)
            current_day = (m.group('mon'), m.group('day'))
            offset = 1
        m = re.match(u'\s*(?P<hour>\d{1,2}):(?P<min>\d{1,2})',
                cells[0 + offset], re.U | re.S)
        value = cells[1 + offset]
        times.append('2011/%s/%s-%s:%s' %
                (current_day[0], current_day[1], m.group('hour'),
                    m.group('min')))
        data.append(value)
    times.reverse()
    data.reverse()
    return times, data


def add_column(levels, new_data):
    times = new_data[0]
    data = new_data[1]
    ii = 0
    levels.append([])
    for jj, ts in enumerate(times):
        while ii < len(levels[0]) and ts > levels[0][ii]:
            levels[-1].append('')
            ii += 1
        levels[0].insert(ii, ts)
        for kk in range(1, len(levels) - 1):
            levels[kk].insert(ii, '-')
        levels[-1].insert(ii, data[jj])
    while ii < len(levels[0]):
        levels[-1].append('')
        ii += 1


def plot_data(places, d_min, d_max, dest_dir):
    p = subprocess.Popen(['gnuplot', '-p'], shell=True, stdin=subprocess.PIPE)
    p.stdin.write('set terminal png size 1024,768\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'ibaraki_levels.png',)))
    p.stdin.write('set xlabel "Time (Day Hour:Minute)"\n')
    p.stdin.write('set timefmt "%Y/%m/%d-%H:%M"\n')
    p.stdin.write('set xdata time\n')
    p.stdin.write('set xrange ["2011/03/14-12:00":]\n')
    p.stdin.write('set format x "%d %H:%M"\n')
    p.stdin.write('set xtics 43200\n')
    p.stdin.write('set ylabel "Microsievert/hour"\n')
    p.stdin.write('set title "Radiation levels in Ibaraki Prefecture (Updated '
            'at %s)"\n' % (time.strftime('%Y/%m/%d %H:%M ' + time.tzname[0],
                time.localtime()),))
    plot_cmd = 'plot '
    for ii, place in enumerate(places):
        plot_cmd += '"levels.dat" u 1:%d title "%s" w l, ' % (ii + 2, place)
    plot_cmd = plot_cmd[:-2] + '\n'
    p.stdin.write(plot_cmd)
    p.stdin.write('set logscale y\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'ibaraki_levels_log.png',)))
    p.stdin.write(plot_cmd)
    p.stdin.write('set terminal png size 640,480\n')
    p.stdin.write('set nologscale y\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'ibaraki_levels_small.png',)))
    p.stdin.write(plot_cmd)
    p.stdin.write('set logscale y\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'ibaraki_levels_log_small.png',)))
    p.stdin.write(plot_cmd)
    p.stdin.write('quit\n')


def main(argv):
    dest_dir = '/home/killbots/killbots.net/random/'
    if (len(argv) > 1):
        dest_dir = argv[1]

    latest_update = get_latest_update()
    url_suffix = latest_update[0]
    time = latest_update[1:]
    places, levels = get_levels(url_suffix)

    places.append('KEK')
    add_column(levels, get_kek())

    aist_data = get_aist()
    if aist_data:
        places.append('AIST')
        add_column(levels, aist_data)

    f = open('levels.dat', 'w')
    for ii in range(len(levels[0])):
        f.write(levels[0][ii].encode('utf-8'))
        for jj in range(1, len(levels)):
            f.write('\t')
            f.write(levels[jj][ii].encode('utf-8'))
        f.write('\n')
    f.close()

    #data_min = min(min(levels[1]), min(levels[2]), min(levels[3]))
    data_min = 0
    data_max = max(max(levels[1]), max(levels[2]), max(levels[3]))

    # Transliterate the places
    t_places = []
    for p in places:
        if p == u'北茨城市':
            t_places.append('Kita Ibaraki City')
        elif p == u'高萩市':
            t_places.append('Takahagi City')
        elif p == u'大子町':
            t_places.append('Daigo Town')
        else:
            t_places.append(p)
    plot_data(tuple(t_places), data_min, data_max, dest_dir)


if __name__ == '__main__':
    main(sys.argv)

