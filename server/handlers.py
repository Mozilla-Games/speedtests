import ConfigParser
import datetime
import json
import os
import re
import speedtests
import templeton.handlers
import urllib2
import web

TESTS_DIR = 'speedtests'

DEFAULT_CONF_FILE = 'speedtests_server.conf'
cfg = ConfigParser.ConfigParser()
cfg.read(DEFAULT_CONF_FILE)
try:
    HTML_URL = cfg.get('speedtests', 'html_url')
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
    HTML_URL = 'http://192.168.1.101/speedtests'
try:
    HTML_DIR = cfg.get('speedtests', 'html_dir')
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
    HTML_DIR = os.path.join('..', 'html')
try:
    SERVER_URL = cfg.get('speedtests', 'server_url')
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
    SERVER_URL = 'http://192.168.1.101/speedtestssvr'
try:
    PROXY_TO = cfg.get('speedtests', 'proxy')
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
    PROXY_TO = None
try:
    RESULTS_ONLY = cfg.get('speedtests', 'results only')
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
    RESULTS_ONLY = False


db = web.database(dbn='mysql', db='speedtests', user='speedtests',
                  pw='speedtests')

urls = ['/testresults/', 'TestResults']
if not RESULTS_ONLY:
    urls.extend([
        '/tests/', 'TestList',
        ])


def query_params():
    params = {}
    if web.ctx.query:
        for q in web.ctx.query[1:].split('&'):
            name, equals, value = q.partition('=')
            if equals:
                params[name] = value
    return params
                    

def test_list():
    """ List of relative paths of test index files. """
    tests = []
    for d in os.listdir(HTML_DIR):
        for f in ('index.html', 'Default.html'):
            if os.path.exists(os.path.join(HTML_DIR, d, f)):
                tests.append(os.path.join(d, f))
                break
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
        

class TestList(object):

    @templeton.handlers.get_json
    def GET(self):
        return test_list()


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

    def POST(self):
        if PROXY_TO:
            self.proxy_request()
            return
        web_data = json.loads(web.data())
        machine_ip = web_data['ip']
        testname = web_data['testname']
        browser_id = get_browser_id(web_data['ua'])
        for results in web_data['results']:
            results['browser_id'] = browser_id
    	    results['ip'] = machine_ip
            cols = {}
            for k, v in results.iteritems():
                cols[k.encode('ascii')] = v
            db.insert(testname, **cols)

    @templeton.handlers.get_json
    def GET(self):
        args, body = templeton.handlers.get_request_parms()
        tables = args.get('testname', None)
        start = args.get('start', None)
        end = args.get('end', None)
        if not tables:
            tables = map(lambda x: os.path.dirname(x), test_list())
        response = {}
        for t in tables:
            wheres = []
            vars = {}
            if start:
                vars['start'] = start[0]
                wheres.append('teststart >= $start')
            if end:
                vars['end'] = end[0]
                wheres.append('teststart <= $end')
            response[t] = map(lambda x: dict(x),
                              db.select(t, vars, where=' AND '.join(wheres)))
            for r in response[t]:
                for k, v in r.iteritems():
                    if isinstance(v, datetime.datetime):
                        r[k] = v.isoformat()
        return response
