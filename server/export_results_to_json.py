#!/usr/bin/env python

import sys
import sets
import math
import getopt
import datetime
import argparse

import ConfigParser
import web
import json

import numpy
import scipy.stats

class DefaultConfigParser(ConfigParser.ConfigParser):
    def get_default(self, section, option, default, func='get'):
        try:
            return getattr(cfg, func)(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default

def parse_range(l):
    result=set()
    for astr in l:
        for part in astr.split(','):
            x=part.split('-')
            result.update(range(int(x[0]),int(x[-1])+1))
    return sorted(result)

DEFAULT_CONF_FILE = 'speedtests_server.conf'
cfg = DefaultConfigParser()

cfg.read(DEFAULT_CONF_FILE)
DB_TYPE = cfg.get_default('server', 'db_type', 'sqlite')
DB_NAME = cfg.get_default('server', 'db_name', 'speedtests.sqlite')
DB_HOST = cfg.get_default('server', 'db_host', 'localhost')
DB_USER = cfg.get_default('server', 'db_user', 'speedtests')
DB_PASSWD = cfg.get_default('server', 'db_passwd', 'speedtests')

def main():
    if DB_TYPE == 'sqlite':
        dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME }
    else:
        dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME, 'db': DB_NAME,
                   'host': DB_HOST, 'user': DB_USER, 'pw': DB_PASSWD }
    db = web.database(**dbargs)
    db.printing = False

    parser = argparse.ArgumentParser()
#    parser.add_argument('-c', '--client', dest='client', action='store', default=None,
#                      help='target client to export', required=True)
#    parser.add_argument('-p', '--platform', dest='platform', action='store', default=None,
#                      help='target platform to export', required=True)
#    parser.add_argument('-b', '--browser', dest='browsers', action='append', default=None,
#                      help='browser name and (optional) version to export', required=True)
#    parser.add_argument('benchmarks', nargs='+', action='store', default=None,
#                      help='benchmarks to export')
    options = parser.parse_args()

    action = """{ "index" : { "_index" : "perfy", "_type" : "scores", "_id" : "1" } }"""
    results = []

    browsers = db.select(['browsers'],
                         what='id, name, version, channel, platform, arch, build')
    browsersById = {}
    for browser in browsers:
        browsersById[browser['id']] = dict(browser)

    runs = db.select(['runs'],
                     what='uuid, browser_id, client, bench_name, start_time',
                     where='complete=1')
    for run in runs:
        uuid = run['uuid']
        run['start_time'] = str(run['start_time'])
        run = dict(run)

        iterations = db.select(['iterations'], {'u': uuid},
                               what='id, iter',
                               where='run_uuid=$u')

        for iteration in iterations:
            iterid = iteration['id']
            iteration = dict(iteration)

            scores = db.select(['scores'], {'i': iterid},
                               what='id, test_name, score, window_width, window_height',
                               where='iteration_id=$i')

            for score in scores:
                result = {
                    'id': '%s:%s:%s' % (run['uuid'], iteration['id'], score['id']),
                    'browser': browsersById[run['browser_id']],
                    'info': {
                        'client': run['client'],
                        'benchmark': run['bench_name'],
                        'started': run['start_time'],
                        'iteration': iteration['iter'],
                        'test': score['test_name'],
                        'window': '%s %s' % (score['window_width'], score['window_height'])
                    },
                    'score': score['score'],
                }
                results.append(result)


    entries = []
    for result in results:
        entry = """{ "index" : { "_index" : "perfy", "_type" : "scores", "_id" : "%s" } }\n%s""" % (result['id'], json.dumps(result))
        entries.append(entry)
    print '\n'.join(entries)
    print '\n'

main()
