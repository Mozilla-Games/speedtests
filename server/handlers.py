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
        '/testpaths/', 'TestPaths')

def query_params():
    params = {}
    if web.ctx.query:
        for q in web.ctx.query[1:].split('&'):
            name, equals, value = q.partition('=')
            if equals:
                params[name] = value
    return params
                    

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
    tests = filter(lambda x: x != 'browser',
                   map(lambda x: x['Tables_in_%s' % DB_NAME],
                       db.query('show tables')))
    tests.sort()
    return tests


def get_browser_id(ua):
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
    
    wheredict = {
        'browsername': bname,
        'browserversion': bver,
        'platform': platform,
        'geckoversion': geckover,
        'buildid': buildid
        }
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
        response = {'clients': [], 'testnames': test_names()}
        if cfg.has_section('clients'):
            response['clients'] = cfg.items('clients')
            response['clients'].sort(key=lambda x: x[1])
        # Could query database for all IPs, but that's slow and probably not
        # useful.
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
        if web_data.get('ignore'):
            return {'result': 'ok'}
        testname = web_data['testname']
        machine_ip = web_data['ip']
        browser_id = get_browser_id(web_data['ua'])
        for results in web_data['results']:
            results['browser_id'] = browser_id
    	    results['ip'] = machine_ip
            cols = {}
            for k, v in results.iteritems():
                cols[k.encode('ascii')] = v
            db.insert(testname, **cols)
        return {'result': 'ok'}

    @templeton.handlers.json_response
    def GET(self):
        args, body = templeton.handlers.get_request_parms()
        tables = args.get('testname', None)
        start = args.get('start', None)
        end = args.get('end', None)
        ip = args.get('ip', None)
        if not tables:
            tables = test_names()
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
            if ip:
                vars['ip'] = ip[0]
                wheres.append('ip like $ip')
            for row in db.select(t, vars, where=' AND '.join(wheres), order='teststart ASC'):
                record = dict(row)
                for k, v in record.iteritems():
                    if isinstance(v, datetime.datetime):
                        record[k] = v.isoformat()
                response['results'][t].append(record)
        return response
