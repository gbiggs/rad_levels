#!/usr/bin/env python
# -*- coding: utf8 -*-

import datetime
import os.path
import re
import subprocess
import sys
import time
import traceback
import urllib2

import cache


CACHE='ibaraki.dat'


def process_cells(cells, dest, current_day, prev_ts):
    # Time stamp
    if cells[0] == u'〜':
        # No data
        return current_day, prev_ts, dest
    # Get a day/time match
    m = re.match(u'((?P<day>\\d{1,2})日\s?)?(?P<hour>\\d{1,2}):(?P<min>\\d{1,2})',
            cells[0], re.U)
    if not m:
        #print ('Warning: Failed to read date from Ibaraki cell "' + cells[0] +
            #'"')
        return current_day, prev_ts, dest
    month = prev_ts.month
    if m.group('day'):
        new_day = int(m.group('day'))
        if new_day < current_day:
            month += 1
        day = new_day
    else:
        day = current_day
    ts = datetime.datetime(2011, month, day, int(m.group('hour')), int(m.group('min')))
    if ts.time() < prev_ts.time() and ts.date() == prev_ts.date():
        # Someone forgot to increment the day at midnight
        ts = ts.replace(day=ts.day + 1)
        day += 1
    for ii, c in enumerate(cells[1:]):
        try:
            val = float(c)
        except ValueError:
            # No data
            continue
        dest.set_value(ts, ii, val)
    return day, ts, dest


def get_latest_update():
    url = 'http://www.pref.ibaraki.jp/important/20110311eq/index.html'
    url_finder = u'href="(?P<url>\\d{8}_\\d{2}.*?/index.html)">.?茨城県\\w?の放射線量の状況'
    html = unicode(urllib2.urlopen(url).read(), 'shift-jis')
    m = re.search(url_finder, html, re.U)
    return m.groups()


def get_levels(url_suffix, dest):
    num_places = 0
    current_day = 1
    prev_ts = datetime.datetime(2011, 4, 1)
    url = 'http://www.pref.ibaraki.jp/important/20110311eq/' + url_suffix
    html = unicode(urllib2.urlopen(url).read(), 'shift-jis')
    # Get the tables dealing with Ibaraki
    tables = re.findall(u'<table.*?>(?P<tables>.*?)</table>',
            html, re.U | re.S)
    for t in tables:
        rows = re.findall(u'<tr>(.*?)</tr>', t, re.U | re.S)
        if num_places == 0:
            # Grab the place names
            places = re.findall(u'<th.*?>.*?（(\w+?)）.*?</th>', rows[0],
                    re.U | re.S)
            # Only need to do this once
            num_places = len(places) / 2

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
                    current_day, prev_ts, dest = process_cells(cells, dest,
                            current_day, prev_ts)
                l_cells = []
                r_cells = []
                page_break = True
                continue
            l_cells.append(cells[:num_places + 1])
            r_cells.append(cells[num_places + 1:])
        for cells in l_cells + r_cells:
            # Process the cells into timestamps and numbers
            current_day, prev_ts, dest = process_cells(cells, dest,
                    current_day, prev_ts)
    return dest


def get_kek(dest):
    url = 'http://rcwww.kek.jp/norm/dose.html'
    html = urllib2.urlopen(url).read()
    value = re.search(r'<b>\s*([\d.]+)', html).group(1)
    time = re.search(r'\((?P<year>\d{4})-(?P<mon>\d{1,2})-(?P<day>\d{1,2}) '
            '(?P<hour>\d{1,2}):(?P<min>\d{1,2})', html)
    dest.set_value(datetime.datetime(int(time.group('year')),
        int(time.group('mon')), int(time.group('day')),
        int(time.group('hour')), int(time.group('min'))), 3, float(value))
    return dest


def get_aist(dest):
    url = 'http://www.aist.go.jp/taisaku/ja/measurement/all_results.html'
    try:
        html = urllib2.urlopen(url).read()
    except urllib2.HTMLError, e:
        print >>sys.stderr, 'Error reading AIST data:', e
        return None
    except httplib.BadStatusLine:
        print >>sys.stderr, 'Error reading AIST data: bad status line'
        return None
    aist_col1 = 4
    aist_col2 = aist_col1 + 1

    table = unicode(re.search(u'<table class="ment".*?>(.*?)</table>', html,
            re.U | re.S).group(1), 'shift-jis')
    rows = re.findall(u'<tr>(.*?)</tr>', table, re.U | re.S)
    current_day = None
    ALL = 0
    COL1 = 1
    COL2 = 2
    mode = ALL
    # Skip the header rows
    for r in rows[2:]:
        cells = re.findall(u'<td ?(.*?>.*?)</td>', r, re.U | re.S)
        m = re.match(u'.*?(?P<mon>\d{1,2})/(?P<day>\d{1,2})',
                cells[0], re.U | re.S)
        if m:
            # Got a new day
            current_day = (int(m.group('mon')), int(m.group('day')))
            cells = cells[1:]
        m = re.match(u'.*?\s*(?P<hour>\d{1,2}):(?P<min>\d{1,2})', cells[0],
                re.U | re.S)
        ts = datetime.datetime(2011, current_day[0], current_day[1],
                int(m.group('hour')), int(m.group('min')))
        cells = cells[1:]
        # Now things get complicated: because they used row-spanning cells we
        # need to track where the span is.
        if len(cells) == 2:
            # Possibly have all data - check the cells to be sure
            if cells[0].find('rowspan') >= 0:
                # First column is going away
                mode = COL2
                # Grab the 2nd column
                val = re.match(r'.*?>(\d+\.?\d*)', cells[1]).group(1)
                dest.set_value(ts, aist_col2, float(val) + 0.06)
            elif cells[1].find('rowspan') >= 0:
                # Second column is going away
                mode = COL1
                # Grab the 1st column
                val = re.match(r'.*?>(\d+\.?\d*)', cells[0]).group(1)
                dest.set_value(ts, aist_col1, float(val) + 0.06)
            else:
                # Have all data
                mode = ALL
                m = re.match(r'.*?>(\d+\.?\d*)', cells[0])
                if m:
                    dest.set_value(ts, aist_col1, float(m.group(1)) + 0.06)
                m = re.match(r'.*?>(\d+\.?\d*)', cells[1])
                if m:
                    dest.set_value(ts, aist_col2, float(m.group(1)) + 0.06)
        else:
            # Have one set of data
            val = re.match(r'.*?>(\d+\.?\d*)', cells[0]).group(1)
            if mode == COL1:
                dest.set_value(ts, aist_col1, float(val) + 0.06)
            else:
                dest.set_value(ts, aist_col2, float(val) + 0.06)
    return dest


def plot_data(places, dest_dir):
    p = subprocess.Popen(['gnuplot', '-p'], shell=True, stdin=subprocess.PIPE)
    p.stdin.write('set terminal png size 1024,768\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'ibaraki_levels.png',)))
    p.stdin.write('set xlabel "Month/Day"\n')
    p.stdin.write('set timefmt "%Y/%m/%d-%H:%M"\n')
    p.stdin.write('set xdata time\n')
    p.stdin.write('set xrange ["2011/03/14-12:00":]\n')
    p.stdin.write('set format x "%m/%d"\n')
    p.stdin.write('set xtics 86400\n')
    p.stdin.write('set ylabel "Microsievert/hour"\n')
    p.stdin.write('set title "Radiation levels in Ibaraki Prefecture (Updated '
            'at %s)"\n' % (time.strftime('%Y/%m/%d %H:%M ' + time.tzname[0],
                time.localtime()),))
    plot_cmd = 'plot '
    for ii, place in enumerate(places):
        plot_cmd += '"%s" u 1:%d title "%s" w l, ' % (CACHE, ii + 2, place)
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
    global CACHE
    dest_dir = '/home/killbots/killbots.net/random/'
    if (len(argv) > 1):
        dest_dir = argv[1]
    CACHE = os.path.join(dest_dir, CACHE)

    data = cache.load_cache(CACHE)
    latest_update = get_latest_update()
    url_suffix = latest_update[0]
    time = latest_update[1:]
    places = ['Kita Ibaraki City', 'Takahagi City', 'Daigo Town', 'KEK',
            'AIST (3F)', 'AIST (Carpark)']
    try:
        data = get_levels(url_suffix, data)
    except:
        traceback.print_exc()
    try:
        data = get_kek(data)
    except:
        traceback.print_exc()
    try:
        data = get_aist(data)
    except:
        traceback.print_exc()
    cache.save_cache(data, CACHE)
    plot_data(places, dest_dir)


if __name__ == '__main__':
    main(sys.argv)

