# -*- coding: utf8 -*-

import datetime
import os.path

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
        if ind == None:
            self._dps.append(DataPoint(timestamp, []))
            self._dps[-1][col] = value
            self._dps[-1].ensure_length(self._col_count)
        else:
            self._dps[ind][col] = value
            self._dps[ind].ensure_length(self._col_count)
        self._dps.sort()

    def sort(self):
        self._dps.sort()


def load_cache(cache_name):
    data = TimeSeries()
    if not os.path.exists(cache_name):
        return data
    f = open(cache_name, 'r')
    for l in f:
        cells = l.split('\t')
        ts = datetime.datetime.strptime(cells[0], '%Y/%m/%d-%H:%M')
        for ii, c in enumerate(cells[1:]):
            if c.strip() != '-':
                data.set_value(ts, ii, c.strip())
    f.close()
    return data


def save_cache(data, cache_name):
    f = open(cache_name, 'w')
    f.write(str(data))
    f.close()

