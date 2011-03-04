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
        '/nexttest/(.*)', 'NextTest'
        )

DEFAULT_CONF_FILE = 'speedtests.conf'
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


class NextTest(object):
    
    def GET(self, current_testname):
        tests = filter(lambda x: os.path.exists(os.path.join(HTML_DIR, x, 'Default.html')), os.listdir(HTML_DIR))
        tests.sort()
        for t in tests:
            if t > current_testname:
                raise web.redirect('%s/%s/Default.html' % (HTML_URL, t))
        raise web.redirect('http://localhost:8111')


def get_browser_id(ua):
    ua = ua.lower()
    platform = 'unknown'
    geckover = 'n/a'
    buildid = 'unknown'
    browserid = 0
    
    if 'firefox' in ua:
        bname = 'Firefox'
        m = re.match('[^\(]*\((.*) rv:([^\)]*)\) gecko/([^ ]+) firefox/(.*)', ua)
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
        m = re.search('chrome/([^ ]*)', ua)
        bver = m.group(1)
    elif 'safari' in ua:
        bname = 'Safari'
        m = re.search('safari/(.*)', ua)
        bver = m.group(1)
    elif 'opera' in ua:
        bname = 'Opera'
        bver = '0.0'
    
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
        results = web_data['results']
        ua = web_data['ua']
        results['browser_id'] = get_browser_id(ua)
        cols = {}
        for k, v in results.iteritems():
            cols[k.encode('ascii')] = v
        db.insert(testname, **cols)


db = web.database(dbn='mysql', db='speedtests', user='speedtests', pw='speedtests')
app = web.application(urls, globals())

if __name__ == '__main__':
    app.run()
