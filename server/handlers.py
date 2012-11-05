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
from collections import defaultdict

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

def get_browser_info(ua, extra_data):
    ua = ua.lower()
    platform = 'unknown'
    geckover = 'n/a'
    buildid = 'unknown'
    browserid = 0
    
    if 'firefox' in ua:
        bname = 'Firefox'
        m = re.match('[^\(]*\((.*) rv:([^\)]*)\) gecko/([^ ]+) firefox/(.*)',
                     ua)
        platform = m.group(1).replace(';', '').strip()
        geckover = m.group(2)
        buildid = m.group(3)
        bver = m.group(4)
    elif 'msie' in ua:
        bname = 'Internet Explorer'
        m = re.search('msie ([^;]*);([^\)]*)\)', ua)
        bver = m.group(1)
        platform = m.group(2).replace(';', '').strip()
    elif 'chrome' in ua:
        bname = 'Chrome'
        m = re.match('mozilla/[^ ]* \(([^\)]*)\).*chrome/([^ ]*)', ua)
        platform = m.group(1).strip()
        bver = m.group(2)
    elif 'safari' in ua:
        bname = 'Safari'
        m = re.match('[^\(]*\(([^\)]*)\).*safari/(.*)', ua)
        platform = m.group(1)
        # 64-bit builds have an extra part separated by a semicolon.
        # Strip it off here rather than making the re much more complicated.
        delim = platform.find(';')
        if delim != -1:
            platform = platform[:delim]
        bver = m.group(2)
    elif 'opera' in ua:
        bname = 'Opera'
        m = re.match('[^\(]*\(([^;]*);[^\)]*\).*version/(.*)', ua)
        platform = m.group(1).strip()
        if platform == 'x11':
            platform = 'linux'
        bver = m.group(2).strip()
    
    browserinfo = {
        'name': bname,
        'version': bver,
        'platform': platform,
        'geckoversion': geckover,
        'buildid': buildid
        }

    # now allow for some overrides
    for token in ['buildid', 'geckoversion', 'sourcestamp', 'screenWidth', 'screenHeight']:
        if token in extra_data:
            browserinfo[token.lower()] = extra_data[token]

    if 'name_extra' in extra_data:
        browserinfo['name'] += "-" + extra_data['name_extra']

    return browserinfo

def get_browser_id(data):
    browserinfo = get_browser_info(data['ua'], data)
    browser = db.select('browsers', where=web.db.sqlwhere(browserinfo))
    # work around some kind of stupid web.py bug or something.
    # checking if browser causes browser[0] to fail afterwards
    # if done directly on the iterator.
    stupid = list(browser)
    if stupid and len(stupid) > 0:
        browser = stupid[0].id
    else:
        browser = db.insert('browsers', **browserinfo)
    return browser

        
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

            # more than one result could have been submitted; it'll always be an array
            for result in data['results']:
                extrajson = None
                error = False
                if 'extra' in result:
                    extrajson = json.dumps(result['raw'])
                    error = result['raw']['error']

                resultdata = {
                    'testname': result['name'],
                    'browser_id': browser_id,
                    'client': client,
                    'window_width': result['width'],
                    'window_height': result['height'],
                    'testtime': testtime,
                    'result_value': result['value'],
                    'extra_data': extrajson,
                    'error': error
                }

                db.insert('results', **resultdata)
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
