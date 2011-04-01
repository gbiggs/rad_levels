#!/usr/bin/env python

import datetime

import cache


f = open('previous.txt', 'r')
lines = f.readlines()[2:]
f.close()

dest = cache.load_cache('fukushima.dat')
for l in lines:
    cells = l.rstrip().split('\t')
    print cells, ' | ',
    ts = datetime.datetime.strptime(cells[1], '%m/%d/%Y %H:%M:%S')
    cells = cells[3:]
    print cells
    for ii, c in enumerate(cells[:7]):
        try:
            float(c.strip())
        except ValueError:
            continue
        dest.set_value(ts, ii, c.strip())
    if len(cells) >= 8:
        dest.set_value(ts, 8, cells[7].strip())
cache.save_cache(dest, 'fukushima.dat')

