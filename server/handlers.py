# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import ConfigParser
import datetime
import json
import os
import re
import speedtests
import templeton.handlers
import urllib2
import web
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
HTML_DIR = cfg.get_default('speedtests', 'html_dir', os.path.join('..', 'html'))
PROXY_TO = cfg.get_default('speedtests', 'proxy', None)
DB_HOST = cfg.get_default('speedtests', 'db_host', 'localhost')
DB_NAME = cfg.get_default('speedtests', 'db_name', 'speedtests')
DB_USER = cfg.get_default('speedtests', 'db_user', 'speedtests')
DB_PASSWD = cfg.get_default('speedtests', 'db_passwd', 'speedtests')
REQUIRE_SIGNED = cfg.get_default('speedtests', 'require_signed', False,
                                 'getboolean')
try:
    CLIENT_KEYS = dict(cfg.items('client keys'))
except ConfigParser.NoSectionError:
    CLIENT_KEYS = {}

if CLIENT_KEYS:
    try:
        import jwt
    except ImportError:
        pass  # FIXME: log this error!

db = web.database(dbn='mysql', host=DB_HOST, db=DB_NAME, user=DB_USER,
                  pw=DB_PASSWD)

urls = ('/testresults/', 'TestResults',
        '/params/', 'Params',
        '/testpaths/', 'TestPaths',
        '/testdetails/', 'TestDetails')

def query_params():
    params = {}
    if web.ctx.query:
        for q in web.ctx.query[1:].split('&'):
            name, equals, value = q.partition('=')
            if equals:
                params[name] = value
    return params

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

def test_paths():
    """ List of relative paths of test index files. """
    tests = []
    for d in os.listdir(HTML_DIR):
        for f in ('index.html', 'Default.html', 'default.html', 'run.html'):
            if os.path.exists(os.path.join(HTML_DIR, d, f)):
                tests.append(os.path.join(d, f))
                break
    tests.sort()
    return tests


def test_names():
    tests = filter(lambda x: x != 'browser' and x != 'generic',
                   map(lambda x: x['Tables_in_%s' % DB_NAME],
                       db.query('show tables')))
    tests.sort()
    return tests

def generic_test_names():
    tests = map(lambda x: x['testname'], db.query('select distinct testname from generic'))
    tests.sort()
    return tests


def get_browser_id(web_data):
    ua = web_data['ua'].lower()
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
    
    wheredict = {
        'browsername': bname,
        'browserversion': bver,
        'platform': platform,
        'geckoversion': geckover,
        'buildid': buildid
        }

    # now allow for some overrides
    for token in ['buildid', 'geckoversion', 'sourcestamp']:
        if token in web_data:
            wheredict[token] = web_data[token]

    if 'name_extra' in web_data:
        wheredict['browsername'] += "-" + web_data['name_extra']

    browser = db.select('browser', where=web.db.sqlwhere(wheredict))
    if not browser:
        db.insert('browser', **wheredict)
        browser = db.select('browser', where=web.db.sqlwhere(wheredict))
    return browser[0].id
        

class TestPaths(object):

    """ Paths of locally served tests. """

    @templeton.handlers.json_response
    def GET(self):
        return test_paths()


class Params(object):

    @templeton.handlers.json_response
    def GET(self):
        # XXX hack.  We don't use the other tests, so we don't bother querying them.
        # Also the ips column might contain an actual name in our case.
        generic_ips = map(lambda x: x['ip'], db.query('select distinct ip from generic'))
        clients = [x[0].capitalize() for x in cfg.items('clients')]
        match_ip = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$')
        for x in generic_ips:
            if not match_ip.match(x):
                clients.append(x)
        clients.sort()

        testnames = test_names() + generic_test_names()
        testnames.sort()

        response = { 'clients': clients, 'testnames': testnames }

        return response


class TestDetails(object):

    @templeton.handlers.json_response
    def GET(self):
        args, body = templeton.handlers.get_request_parms()
        testids = simple_ascii_only(args.get('testids', None))
        if testids is None:
            return None
        testids = map(lambda x: str(int(x)), testids[0].split(","))
        response = { }
        rows = db.query("SELECT * FROM generic WHERE id IN (" + ",".join(testids) + ")");
        for row in rows:
            record = dict(row)
            for k, v in record.iteritems():
                if isinstance(v, datetime.datetime):
                    record[k] = v.isoformat()
            record['result_data'] = json.loads(record['result_data'])
            response[record['id']] = record
        return response

class TestResults(object):

    def proxy_request(self):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate'
            }
        # FIXME: Error logging
        request = urllib2.Request(PROXY_TO, web.data(), headers)
        response = urllib2.urlopen(request, timeout=120).read()

    @templeton.handlers.json_response
    def POST(self):
        if PROXY_TO:
            self.proxy_request()
            return
        content_type = web.ctx.env.get('CONTENT_TYPE', '')
        if content_type == 'application/jwt':
            token = jwt.decode(web.data(),
                               signers=[jwt.jws.HmacSha(keydict=CLIENT_KEYS)])
            if not token['valid']:
                # JWT signature not valid
                # FIXME: Log error!
                return {'result': 'error', 'error': 'invalid signature'}
            web_data = token['payload']
        elif REQUIRE_SIGNED:
            return {'result': 'error', 'error': 'results must be signed'}
        else:
            web_data = json.loads(web.data())
        #print "POST: " + str(web_data)
        if web_data.get('ignore'):
            return {'result': 'ok'}
        testname = web_data['testname']
        machine_ip = web_data['ip']
        machine_client = web_data['client']
        browser_id = get_browser_id(web_data)

        for results in web_data['results']:
            r = results
            tablename = testname
            if 'value' in results:
                r = {}
                r['browser_id'] = browser_id
                r['ip'] = machine_client # not machine_ip
                r['browser_height'] = results['browser_height']
                r['browser_width'] = results['browser_width']
                r['teststart'] = results['teststart']
                r['testname'] = testname
                r['result_value'] = results['value']
                r['result_data'] = json.dumps(results['raw'])
                tablename = 'generic'
            else:
                r['browser_id'] = browser_id
                r['ip'] = machine_client
            cols = {}
            for k, v in r.iteritems():
                cols[k.encode('ascii')] = v
            # web.py is a piece of shit that builds up sql inserts/queries by adding
            # strings together, so we can't just use db.insert because it's basically
            # begging to be exploited (and gets any strings that have complicated things
            # in them wrong
            ###db.insert(tablename, **cols)

            colkeys = cols.keys()
            colvals = []
            for i in range(len(colkeys)):
                colvals.append(cols[colkeys[i]])
            cursor = db.ctx.db.cursor()
            sql_query = "INSERT INTO " + tablename + " (" + (",".join(colkeys)) + ") VALUES (" + (",".join(['%s'] * len(colkeys))) + ")";
            cursor.execute(sql_query, tuple(colvals))
            db.ctx.db.commit()
            cursor.close()

        return {'result': 'ok'}

    @templeton.handlers.json_response
    def GET(self):
        args, body = templeton.handlers.get_request_parms()
        tables = simple_ascii_only(args.get('testname', None))
        start = simple_ascii_only(args.get('start', None))
        end = simple_ascii_only(args.get('end', None))
        client = simple_ascii_only(args.get('client', None))
        fullresults = simple_ascii_only(args.get('full', False))
        gentests = generic_test_names()
        if not tables:
            tables = test_names() + gentests
        for i in range(len(tables)):
            if tables[i] in gentests:
                tables[i] = ["generic", tables[i].encode('ascii')]

        response = { 'browsers': {},
                     'results': defaultdict(list) }
        for row in db.select('browser'):
            response['browsers'][row['id']] = dict(row)
        for t in tables:
            wheres = []
            vars = {}
            if start:
                vars['start'] = start[0]
                wheres.append('teststart >= $start')
            if end:
                vars['end'] = end[0]
                # if just a date is passed in (as opposed to a full datetime),
                # we want it to be *inclusive*, i.e., returning all results
                # on that date.
                if re.match('\d{4}-\d{2}-\d{2}$', vars['end']):
                    wheres.append('date(teststart) <= $end')
                else:
                    wheres.append('teststart <= $end')
            if client:
                client_wheres = []
                try:
                    ips = [x.strip() for x in
                           cfg.get('clients',client[0]).split(',')]
                except ConfigParser.NoOptionError:
                    ips = []
                    
                for i, ip in enumerate(ips):
                    vars['ip%d' % i] = ip
                    client_wheres.append('ip like $ip%d' % i)

                if len(client_wheres) == 0:
                    # note that we already applied simple_ascii_only to client, so this is safe
                    client = client[0].split(",")
                    wheres.append("ip in ('" + "','".join(client) + "')")
                else:
                    wheres.append('(' + ' OR '.join(client_wheres) + ')')

            tablename = t
            testname = t
            if type(t) is not str:
                tablename = t[0]
                testname = t[1]
                wheres.append("testname = '%s'" % (testname))

            #print "WHERE", ' AND '.join(wheres)

            result = db.select(tablename, vars, where=' AND '.join(wheres), order='teststart ASC')
            for row in result:
                record = dict(row)
                for k, v in record.iteritems():
                    if isinstance(v, datetime.datetime):
                        record[k] = v.isoformat()
                # no need to send this with each line
                record.pop('testname', False)
                # and don't send the full data unless explicitly requested
                if not fullresults:
                    record.pop('result_data', False)
                response['results'][testname].append(record)
        return response
