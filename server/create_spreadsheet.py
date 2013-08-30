#!/usr/bin/env python

import sys
import json
import argparse
import datetime

import numpy
import scipy.stats
import xlwt

DECIMAL_FMT = '0.00'

def mean_confidence_interval(data, confidence=0.95):
    a = 1.0*numpy.array(data)
    n = len(a)
    m, se = numpy.mean(a), scipy.stats.sem(a)
    h = se * scipy.stats.t._ppf((1+confidence)/2., n-1)
    return m-h, m+h

class Sheet:
    def __init__(self, wb, bench):
        self.bench = bench
        self.headers = ['time', 'client', 'platform', 'arch', 'browser', 'version', 'build']
        self.rows = []
        self.ws = wb.add_sheet(bench)

    def append_header(self, header):
        self.headers.append(header)

    def extend_headers(self, headers):
        self.headers.extend(headers)

    def insert_row(self, row):
        self.rows.append(row)

    def write(self):
        style = xlwt.XFStyle()
        style.num_format_str = DECIMAL_FMT

        for i in range(0, len(self.headers)):
            self.ws.write(0, i, self.headers[i])

        for i in range(0, len(self.rows)):
            for j in range(0, len(self.rows[i])):
                self.ws.write(i+1, j, self.rows[i][j], style)

def create_spreadsheet(data, out):
    wb = xlwt.Workbook()
    browser_data = {}

    for (id, info) in data['browsers'].items():
        browser_data[id] = info

    for bench, browsers in data['scores'].items():
        ws = Sheet(wb, bench)

        doheaders = True
        for bid, results in browsers.items():
            if doheaders:
                headers = results['scores'].keys()
                #error_headers = [x + '_stderr' for x in headers]
                ci_headers = [y + '_ci' for y in headers]
                headers.extend(ci_headers)
                ws.extend_headers(headers)
                doheaders = False
            row = [results['start_time'], data['client'], browser_data[bid]['platform'], browser_data[bid]['arch'], browser_data[bid]['name'], browser_data[bid]['version'], browser_data[bid]['build']]
            i = len(row)
            for subbench, iters in results['scores'].items():
                values = [it['score'] for it in iters.values()]
                if len(values) > 1:
                    avg = numpy.average(values)
                    err = scipy.stats.sem(values)
                    ci = mean_confidence_interval(values)
                else:
                    avg = values[0]
                    err = '?'
                    ci = ('?', '?')
                row.insert(i, avg)
                #row.append(err)
                row.append("%s, %s" % ci)
                i += 1

            ws.insert_row(row)

        ws.write()

    wb.save(out)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--out', dest='out', action='store', default=None,
                      help='output file name', required=True)
    options = parser.parse_args()

    create_spreadsheet(json.loads(sys.stdin.read()), options.out)