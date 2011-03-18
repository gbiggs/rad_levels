#!/usr/bin/env python

import datetime


f = open('previous.txt', 'r')
lines = f.readlines()[2:]
f.close()

f = open('output.txt', 'w')
for l in lines:
    cells = l.rstrip().split('\t')
    date = datetime.datetime.strptime(cells[1], '%m/%d/%Y %H:%M:%S')
    cells = cells[3:]
    data_str = '%04d/%02d/%02d-%02d:%02d\t' % (date.year, date.month, date.day,
            date.hour, date.minute)
    print cells
    for c in cells[:7]:
        try:
            float(c)
        except ValueError:
            data_str += '-\t'
            continue
        data_str += c + '\t'
    if len(cells) < 7:
        for ii in range(len(cells), 7):
            data_str += '-\t'
    data_str += '-\t'
    if len(cells) >= 8:
        data_str += cells[7]
    else:
        data_str += '-'
    data_str += '\t-\t-\t-\t-\n'
    f.write(data_str)
f.close()

