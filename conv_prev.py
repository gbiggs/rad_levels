#!/usr/bin/env python

import datetime

import cache


f = open('previous.txt', 'r')
lines = f.readlines()[2:]
f.close()

dest = cache.load_cache('fukushima.dat')
for l in lines:
    cells = l.rstrip().split('\t')
    ts = datetime.datetime.strptime(cells[1], '%m/%d/%Y %H:%M:%S')
    cells = cells[3:]
    for ii, c in enumerate(cells[:7]):
        try:
            float(c.strip())
        except ValueError:
            continue
        dest.set_value(ts, ii, c.strip())
        data_str += c + '\t'
    if len(cells) >= 8:
        dest.set_value(ts, 7, cells[7].strip())
cache.save_cache(dest, 'fukushima.dat')

