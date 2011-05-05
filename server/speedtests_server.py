#!/usr/bin/env python2.6
import ConfigParser
import json
import os
import re
import web
import speedtests

TESTS_DIR = 'speedtests'

urls = (
        '/testresults/', 'TestResults',
        '/nexttest/(.*)', 'NextTest',
        '/start/', 'StartTests',
        '/done/', 'DoneTests'
        )

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


class NextTest(object):
    
    def GET(self, current_testname):
        params = {}
        if web.ctx.query:
            for q in web.ctx.query[1:].split('&'):
                name, equals, value = q.partition('=')
                if equals:
                    params[name] = value
                    
        # The start page is new and launches the tests in a new window with a
        # set size.  For anyone going straight to /nexttest/, we'll redirect
        # them to the start page.  The start page will include the search
        # string 'runtests=true' to actually load the next test. 
        if not params.get('runtests', False):
            raise web.seeother('%s/start/' % SERVER_URL)

        tests = filter(lambda x: os.path.exists(os.path.join(HTML_DIR, x, 'Default.html')), os.listdir(HTML_DIR))
        tests.sort()
        for t in tests:
            if t > current_testname:
                raise web.seeother('%s/%s/Default.html%s' % (HTML_URL, t, web.ctx.query))
        if params.get('auto', False):
            # Redirect to the local server to start the next browser.
            # We can't use localhost here because IE has issues connecting to the server via
            # localhost.
            raise web.seeother('http://%s:%s/' % (params['ip'], params['port']))
        raise web.seeother('%s/done/' % SERVER_URL) 


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
        m = re.match('[^\(]*\(([^;]*);[^\)]*\).*safari/(.*)', ua)
        platform = m.group(1)
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
        

class TestResults(object):
    
    def POST(self):
        web_data = json.loads(web.data())
        testname = web_data['testname']
        browser_id = get_browser_id(web_data['ua'])
        for results in web_data['results']:
            results['browser_id'] = browser_id
    	    results['ip'] = web.ctx.ip
            cols = {}
            for k, v in results.iteritems():
                cols[k.encode('ascii')] = v
            db.insert(testname, **cols)


class StartTests(object):
    
    def GET(self):
        start = web.template.frender('templates/start.html')
        return start(SERVER_URL, HTML_URL)


class DoneTests(object):
    
    def GET(self):
        done = web.template.frender('templates/done.html')
        return done(SERVER_URL, HTML_URL)


db = web.database(dbn='mysql', db='speedtests', user='speedtests',
                  pw='speedtests')
app = web.application(urls, globals())

if __name__ == '__main__':
    app.run()
