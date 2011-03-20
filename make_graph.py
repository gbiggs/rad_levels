#!/usr/bin/env python
# -*- coding: utf8 -*-

import datetime
import os.path
import re
import subprocess
import sys
import time
import urllib2


class DataPoint(object):
    def __init__(self, timestamp, values):
        self._ts = timestamp
        self._vals = values

    def __repr__(self):
        return 'DataPoint(datetime.datetime(%04d, %02d, %02d, %02d, %02d), %s)' % \
                (self._ts.year, self._ts.month, self._ts.day, self._ts.hour,
                        self._ts.minute, repr(self._vals))

    def __str__(self):
        res = '%04d/%02d/%02d-%02d:%02d\t' % (self._ts.year, self._ts.month,
                self._ts.day, self._ts.hour, self._ts.minute)
        for v in self._vals:
            res += '%s\t' % (str(v),)
        return res[:-1]

    def __len__(self):
        return len(self._vals)

    def __getitem__(self, index):
        if index >= len(self._vals) or index < -len(self._vals):
            raise IndexError
        return self._vals[index]

    def __setitem__(self, index, value):
        if index < 0:
            index = len(self._vals) + index
        for ii in range(len(self._vals), index + 1):
            self._vals.append('-')
        self._vals[index] = value

    def __lt__(self, other):
        return self._ts < other.timestamp

    def __le__(self, other):
        return self._ts <= other.timestamp

    def __eq__(self, other):
        return self._ts == other.timestamp

    def __ne__(self, other):
        return self._ts != other.timestamp

    def __gt__(self, other):
        return self._ts > other.timestamp

    def __ge__(self, other):
        return self._ts >= other.timestamp

    @property
    def timestamp(self):
        return self._ts

    def ensure_length(self, min_len):
        while len(self._vals) < min_len:
            self._vals.append('-')


class TimeSeries(object):
    def __init__(self):
        self._dps = [] # This should really be a binary tree
        self._col_count = 0

    def __str__(self):
        res = ''
        for dp in self._dps:
            res += '%s\n' % (str(dp),)
        return res[:-1]

    def __len__(self):
        return len(self._dps)

    def num_cols(self):
        '''Returns the number of values in a data point.'''
        if not self._dps:
            return 0
        return len(self._dps[0])

    def ts_index(self, timestamp):
        for ii, dp in enumerate(self._dps):
            if dp.timestamp == timestamp:
                return ii
        return None

    def set_value(self, timestamp, col, value):
        if self._col_count < col + 1:
            for dp in self._dps:
                dp.ensure_length(col + 1)
            self._col_count = col + 1
        if len(self._dps) > 0 and timestamp > self._dps[-1].timestamp:
            # Optimisation for data that is coming in in increasing time order
            ind = None
        else:
            ind = self.ts_index(timestamp)
        if not ind:
            self._dps.append(DataPoint(timestamp, []))
            self._dps[-1][col] = value
            self._dps[-1].ensure_length(self._col_count)
        else:
            self._dps[ind][col] = value
            self._dps[ind].ensure_length(self._col_count)
        self._dps.sort()

    def sort(self):
        self._dps.sort()


def load_cache():
    data = TimeSeries()
    f = open('ibaraki.dat', 'r')
    for l in f:
        cells = l.split('\t')
        ts = datetime.datetime.strptime(cells[0], '%Y/%m/%d-%H:%M')
        for ii, c in enumerate(cells[1:]):
            if c.strip() != '-':
                data.set_value(ts, ii, c.strip())
    f.close()
    return data


def save_cache(data):
    f = open('ibaraki.dat', 'w')
    f.write(str(data))
    f.close()


def process_cells(cells, dest, current_day, prev_ts, expected_len):
    # Time stamp
    if cells[0] == u'〜':
        # No data
        return current_day, prev_ts, dest
    # Get a day/time match
    m = re.match(u'((?P<day>\\d{1,2})日\s?)?(?P<hour>\\d{1,2}):(?P<min>\\d{1,2})',
            cells[0], re.U)
    if m.group('day'):
        current_day = int(m.group('day'))
    day = current_day
    ts = datetime.datetime(2011, 3, day, int(m.group('hour')), int(m.group('min')))
    if ts < prev_ts:
        # Someone forgot to increment the day at midnight
        ts = ts.replace(day=ts.day + 1)
        current_day += 1
    for ii, c in enumerate(cells[1:]):
        try:
            val = float(c)
        except ValueError:
            # No data
            continue
        dest.set_value(ts, ii, val)
    return current_day, ts, dest


def get_latest_update():
    url = 'http://www.pref.ibaraki.jp/important/20110311eq/index.html'
    url_finder = u'href="(?P<url>\\d{8}_\\d{2}.*?/index.html)">.?茨城県\\w?の放射線量の状況'
    html = unicode(urllib2.urlopen(url).read(), 'shift-jis')
    m = re.search(url_finder, html, re.U)
    return m.groups()


def get_levels(url_suffix, dest):
    places = []
    num_places = 0
    current_day = None
    prev_ts = datetime.datetime(2000, 1, 1)
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
                    current_day, prev_ts, dest = process_cells(cells, dest,
                            current_day, prev_ts, num_places)
                l_cells = []
                r_cells = []
                page_break = True
                continue
            l_cells.append(cells[:num_places + 1])
            r_cells.append(cells[num_places + 1:])
        for cells in l_cells + r_cells:
            # Process the cells into timestamps and numbers
            current_day, prev_ts, dest = process_cells(cells, dest,
                    current_day, prev_ts, num_places)
    return places, dest


def get_kek(dest):
    url = 'http://rcwww.kek.jp/norm/dose.html'
    html = urllib2.urlopen(url).read()
    value = re.search(r'<b>\s*([\d.]+)', html).group(1)
    time = re.search(r'\((?P<mon>\d{1,2})/(?P<day>\d{1,2}) '
            '(?P<hour>\d{1,2}):(?P<min>\d{1,2})', html)
    dest.set_value(datetime.datetime(2011, int(time.group('mon')),
        int(time.group('day')), int(time.group('hour')),
        int(time.group('min'))), 3, float(value))
    return dest


def get_aist(places, dest):
    url = 'http://www.aist.go.jp/taisaku/ja/measurement/all_results.html'
    try:
        html = urllib2.urlopen(url).read()
    except urllib2.HTMLError, e:
        print >>sys.stderr, 'Error reading AIST data:', e
        return None
    except httplib.BadStatusLine:
        print >>sys.stderr, 'Error reading AIST data: bad status line'
        return None
    places.append('AIST (3F)')
    places.append('AIST (Carpark)')
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
        m = re.match(u'.*?(?P<mon>\d{1,2})月(?P<day>\d{1,2})日',
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
                val = re.match(r'.*?>(\d+\.?\d*)', cells[0]).group(1)
                dest.set_value(ts, aist_col1, float(val) + 0.06)
                val = re.match(r'.*?>(\d+\.?\d*)', cells[1]).group(1)
                dest.set_value(ts, aist_col2, float(val) + 0.06)
        else:
            # Have one set of data
            val = re.match(r'.*?>(\d+\.?\d*)', cells[0]).group(1)
            if mode == COL1:
                dest.set_value(ts, aist_col1, float(val) + 0.06)
            else:
                dest.set_value(ts, aist_col2, float(val) + 0.06)
    return places, dest


def add_column(levels, new_data):
    times = new_data[0]
    data = new_data[1]
    ii = 0
    levels.append([])
    for jj, ts in enumerate(times):
        while ii < len(levels[0]) and ts > levels[0][ii]:
            levels[-1].append('')
            ii += 1
        if ts == levels[0][ii]:
            levels[-1].insert(ii, data[jj])
        else:
            levels[0].insert(ii, ts)
            for kk in range(1, len(levels) - 1):
                levels[kk].insert(ii, '-')
            levels[-1].insert(ii, data[jj])
    while ii < len(levels[0]):
        levels[-1].append('')
        ii += 1


def plot_data(places, dest_dir):
    p = subprocess.Popen(['gnuplot', '-p'], shell=True, stdin=subprocess.PIPE)
    p.stdin.write('set terminal png size 1024,768\n')
    p.stdin.write('set output "%s"\n' %
            (os.path.join(dest_dir, 'ibaraki_levels.png',)))
    p.stdin.write('set xlabel "Day"\n')
    p.stdin.write('set timefmt "%Y/%m/%d-%H:%M"\n')
    p.stdin.write('set xdata time\n')
    p.stdin.write('set xrange ["2011/03/14-12:00":]\n')
    p.stdin.write('set format x "%d"\n')
    p.stdin.write('set xtics 86400\n')
    p.stdin.write('set ylabel "Microsievert/hour"\n')
    p.stdin.write('set title "Radiation levels in Ibaraki Prefecture (Updated '
            'at %s)"\n' % (time.strftime('%Y/%m/%d %H:%M ' + time.tzname[0],
                time.localtime()),))
    plot_cmd = 'plot '
    for ii, place in enumerate(places):
        plot_cmd += '"ibaraki.dat" u 1:%d title "%s" w l, ' % (ii + 2, place)
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

    data = load_cache()
    latest_update = get_latest_update()
    url_suffix = latest_update[0]
    time = latest_update[1:]
    places, data = get_levels(url_suffix, data)
    places.append('KEK')
    data = get_kek(data)
    places, data = get_aist(places, data)
    save_cache(data)

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
    plot_data(tuple(t_places), dest_dir)


if __name__ == '__main__':
    main(sys.argv)

