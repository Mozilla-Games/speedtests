# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import ConfigParser
import time
import datetime
import json
import os
import re
import templeton.handlers
import urllib2
import web
import base64
import traceback
import logging
from collections import defaultdict
from ua_parser import user_agent_parser

def parse_ua(ua_string):
    result = user_agent_parser.Parse(ua_string)

    if('x86_64' in result['string']):
        result['os']['arch'] = 'x86_64'
    else:
        result['os']['arch'] = ''

    return result

class DefaultConfigParser(ConfigParser.ConfigParser):

    def get_default(self, section, option, default, func='get'):
        try:
            return getattr(cfg, func)(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default

TESTS_DIR = 'speedtests'

DEFAULT_CONF_FILE = 'speedtests_server.conf'
cfg = DefaultConfigParser()

cfg.read(DEFAULT_CONF_FILE)
DB_TYPE = cfg.get_default('server', 'db_type', 'sqlite')
DB_NAME = cfg.get_default('server', 'db_name', 'speedtests.sqlite')
DB_HOST = cfg.get_default('server', 'db_host', 'localhost')
DB_USER = cfg.get_default('server', 'db_user', 'speedtests')
DB_PASSWD = cfg.get_default('server', 'db_passwd', 'speedtests')

if DB_TYPE is 'sqlite':
    dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME }
else:
    dbargs = { 'dbn': DB_TYPE, 'db': DB_NAME, 'db': DB_NAME, 'host': DB_HOST, 'user': DB_USER, 'pw': DB_PASSWD }
db = web.database(**dbargs)

# let's just make things work if the db is empty
try:
    db.query('SELECT COUNT(*) FROM browsers')
except:
    schema_lines = "".join(open("schema.sql", "r").readlines()).split(";")
    cursor = db.ctx.db.cursor()
    for line in schema_lines:
        cursor.execute(line)
    db.ctx.db.commit()
    cursor.close()
    print "Initialized empty sqlite database."

try:
    db.query('SELECT COUNT(*) FROM browsers')
except:
    print "Tried to initialize empty database, but failed!"
    raise

urls = ('/testinfo/', 'TestInfo',
        '/testresults/', 'TestResults',
        '/testdetails/', 'TestDetails',
        '/submit-result/', 'SubmitResult')

# nuke everything but a-z A-Z 0-9 _ . , - and space'
# at the very least it should be safe for sql (inside strings)
def simple_ascii_only(val):
    if type(val) is list:
        for i in range(len(val)):
            val[i] = simple_ascii_only(val[i])
        return val

    if type(val) is not str and type(val) is not unicode:
        return val

    val = val.encode('ascii')
    return re.sub(r'[^a-zA-Z0-9_., -]', '', val)

def test_names():
    tests = map(lambda x: x['testname'], db.query('SELECT DISTINCT testname FROM results'))
    tests.sort()
    return tests

def get_browser_info(ua_string, extra_data):
    ua = parse_ua(ua_string)

    bname = ua['user_agent']['family']
    bver = ua['user_agent']['major']
    platform = ua['os']['family']
    arch = ua['os']['arch']

    browserinfo = {
        'name': bname,
        'version': bver,
        'platform': platform,
        'arch': arch
        }

    if not 'Firefox' in bname:
        browserinfo['build'] = '%s.%s.%s' % (ua['user_agent']['major'], ua['user_agent']['minor'], ua['user_agent']['patch'])

    # add some extra info bits
    for token in ['screenWidth', 'screenHeight']:
        if token in extra_data:
            browserinfo[token.lower()] = extra_data[token]

    for token in ['BuildID', 'SourceStamp']:
        if ("browser" + token) in extra_data:
            browserinfo[token.lower()] = extra_data["browser" + token]

    if 'browserNameExtra' in extra_data:
        browserinfo['name'] += "-" + extra_data['browserNameExtra']

    #print json.dumps(browserinfo)

    return browserinfo

def get_browser_id(data):
    browserinfo = get_browser_info(data['ua'], data)
    if not 'build' in browserinfo:
        browserinfo['build'] = data['build']
    browser = db.select('browsers', where=web.db.sqlwhere(browserinfo))
    # work around some kind of stupid web.py bug or something.
    # checking if browser causes browser[0] to fail afterwards
    # if done directly on the iterator.
    browser = list(browser)
    if browser and len(browser) > 0:
        return browser[0].id
    return db.insert('browsers', **browserinfo)

def get_bench_run(config, browser_id):
    run_uuid = config['run_uuid']
    client = config['client']
    bench_name = config['bench_name']
    run = db.select('runs', where=web.db.sqlwhere({'uuid':run_uuid}))
    run = list(run)
    if run and len(run) > 0:
        run = run[0]
        # verify that existing run and new run matches on other info.
        if run.browser_id != browser_id:
            logging.warn("Browser mismatch: run=%s db=%s got=%s" % (run_uuid, run.browser_id, browser_id))
            return
        if run.client != client:
            logging.warn("Client mismatch: run=%s db=%s got=%s" % (run_uuid, run.client, client))
            return
        if run.bench_name != bench_name:
            logging.warn("Bench mismatch: run=%s db=%s got=%s" % (run_uuid, run.bench_name, bench_name))
            return
    else:
        db.insert('runs',
            uuid=run_uuid,
            browser_id=browser_id,
            client=client,
            bench_name=bench_name,
            start_time=datetime.datetime.now().isoformat().replace("T", " "),
            complete=0
        )
    return run_uuid

def get_bench_iteration(config, run_uuid):
    # search for the highest 'iter' among existing iterations for this run.
    iterations = db.select('iterations', where=web.db.sqlwhere({'run_uuid':run_uuid}))
    iterations = list(iterations)
    def cmp_iterations(a, b):
        return cmp(a.iter, b.iter)
    iterations.sort(cmp_iterations)
    iter_no = 1
    if len(iterations) > 0:
        iter_no = iterations[-1].iter + 1
    # insert new iteartion entry
    iter_id = db.insert('iterations', run_uuid=run_uuid, iter=iter_no)
    return iter_id

class SubmitResult(object):
    def GET(self):
        args, body = templeton.handlers.get_request_parms()
        # we ignore body, it should be empty; everything's done via GET

        target = args['target'][0]
        data = json.loads(base64.b64decode(args['data'][0]))

        # the data object contains (see speedtests.js for 100% accurate info):
        #   browserInfo: {ua, screenWidth, screenHeight}
        #   config: the full config object that was passed to each test; this has details
        #     like clientName and platform, which we'll need
        #   loadTime: time to load the test
        #   startTime: time that init() was called
        #   finishTime: time that finish() was called
        #   results: array of objects, each containing:
        #     value: the actual final value of the test
        #     raw: [optionally] the full set of periodic values
        #     width: window.innerWidth at the time the result was recorded
        #     height: window.innerHeight at the time the result was recorded
        #     extra: an object containing any extra data the test returned

        client = data['config']['clientName']

        transaction = db.transaction()
        try:
            # get or create a browser_id
            browser_id = get_browser_id(data['browserInfo'])
            testtime = datetime.datetime.utcfromtimestamp(data['startTime'] / 1000.0)
            # the replacement is needed for sqlite
            testtime = testtime.isoformat().replace("T", " ")

            # get or create a run for this data.
            run_uuid = get_bench_run(data['config'], browser_id)

            # get or create an iteration for this data.
            iter_id = get_bench_iteration(data['config'], run_uuid)

            complete = data['complete']
            if complete:
                db.update('runs', where='uuid=%s' % complete=1)

            # more than one result could have been submitted; it'll always be an array
            for result in data['results']:
                extrajson = None
                error = False
                if 'extra' in result:
                    extrajson = json.dumps(result['extra'])
                    if 'error' in result['extra']:
                        error = result['extra']['error']

                scoredata = {
                    'iteration_id': iter_id,
                    'test_name': result['name'],
                    'score': result['value'],
                    'window_width': result['width'],
                    'window_height': result['height'],
                    'extra_data': extrajson
                }

                db.insert('scores', **scoredata);
        except:
            transaction.rollback()
            raise
        else:
            transaction.commit()

        # Send the response with the JS to set the flag to Done
        return 'SpeedTests["%s" + "Done"] = true;' % (target)

class TestInfo(object):
    @templeton.handlers.json_response
    def GET(self):
        clients = map(lambda row: row['client'], db.query('SELECT DISTINCT client FROM results'))
        clients.sort()
        testnames = test_names()

        return { 'clients': clients, 'testnames': testnames }

class TestDetails(object):
    @templeton.handlers.json_response
    def GET(self):
        args, body = templeton.handlers.get_request_parms()
        testids = args.get('testids', None)
        if testids is None:
            return None
        testids = map(lambda x: str(int(x)), testids[0].split(","))
        response = { }
        rows = db.query("SELECT * FROM results WHERE id IN " + web.db.sqlquote(testids));
        for row in rows:
            record = dict(row)
            for k, v in record.iteritems():
                if isinstance(v, datetime.datetime):
                    record[k] = time.mktime(v.timetuple()) * 1000
            record['extra_data'] = json.loads(record['extra_data'])
            response[record['id']] = record
        return response

class TestResults(object):
    @templeton.handlers.json_response
    def GET(self):
        args, body = templeton.handlers.get_request_parms()
        testnames = simple_ascii_only(args.get('testname', None))
        start = simple_ascii_only(args.get('start', None))
        end = simple_ascii_only(args.get('end', None))
        clients = simple_ascii_only(args.get('client', None))
        fullresults = simple_ascii_only(args.get('full', False))

        wheres = []
        vars = {}
        if start:
            vars['start'] = start[0]
            wheres.append('date(testtime) >= date($start)')

        if end:
            vars['end'] = end[0]
            # if just a date is passed in (as opposed to a full datetime),
            # we want it to be *inclusive*, i.e., returning all results
            # on that date.
            if re.match('\d{4}-\d{2}-\d{2}$', vars['end']):
                wheres.append('date(testtime) <= date($end)')
            else:
                wheres.append('date(testtime) < date($end)')

        if clients:
            clients = clients[0].split(',')
            wheres.append("client IN " + web.db.sqlquote(clients))

        if testnames:
            testnames = testnames[0].split(',')
            wheres.append("testname IN " + web.db.sqlquote(testnames))

        if len(wheres) == 0:
            return dict()

        response = { 'browsers': {},
                     'results': defaultdict(list) }

        browserset = set()

        result = db.select("results", vars, where=' AND '.join(map(lambda x: str(x), wheres)), order='testtime ASC')
        for row in result:
            record = dict(row)
            browserset.add(record['browser_id'])

            for k, v in record.iteritems():
                if isinstance(v, datetime.datetime):
                    record[k] = time.mktime(v.timetuple()) * 1000

            # no need to send this with each line; we'll know it based on the key
            testname = record.pop('testname', False)

            # and don't send the full data unless explicitly requested
            if not fullresults:
                record.pop('extra_data', False)

            if not testname in response['results']:
                response['results'][testname] = list()
            response['results'][testname].append(record)

        result = db.query("SELECT * FROM browsers WHERE id IN " + web.db.sqlquote(list(browserset)))
        for row in result:
            record = dict(row)
            response['browsers'][record['id']] = record

        return response
