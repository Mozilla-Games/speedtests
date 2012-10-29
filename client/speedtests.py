# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import SocketServer
import BaseHTTPServer
import cgi
import collections
import ConfigParser
import datetime
import errno
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib
import urllib2
import zipfile
import StringIO

from Config import config
from BrowserRunner import *
from BrowserController import *
import results


class TestRunnerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    
    def do_GET(self):
        print "Handling GET '%s'..." % (self.path)
        if self.path.startswith(config.local_test_base_path):
            try:
                url = config.server_html_url + self.path[len(config.local_test_base_path):]
                u = urllib2.urlopen(url)
            except urllib2.HTTPError, e:
                self.send_response(e.getcode())
            else:
                data = u.read()
                self.send_response(200)
                for header, value in u.info().items():
                    self.send_header(header, value)
                self.end_headers()
                self.wfile.write(data)
        else:
            print "Invalid URL request: " + self.path
            self.send_response(404)
        print "...done (GET)."

    def do_POST(self):
        print "Handling POST '%s'..." % (self.path)
        length = int(self.headers.getheader('content-length'))
        web_data = json.loads(self.rfile.read(length))

        # if this was skipped, we've got nothing to do
        if 'test_skipped' in web_data and web_data['test_skipped']:
            print "Test was skipped."
            self.send_response(200)
            self.end_headers()
            self.wfile.write('<html></html>')
            self.server.browser_runner.next_test()
            print "...done. (skipped)"
            return

        if config.ignore:
            web_data['ignore'] = True
        testname = web_data['testname']
        self.server.results[self.server.browser_runner.browser_name()][testname].extend(web_data['results'])
        if not config.testmode and not config.noresults:
            web_data.update(self.server.standard_web_data())
            if self.server.browser_runner.current_controller.AppSourceStamp:
                web_data['sourcestamp'] = self.server.browser_runner.current_controller.AppSourceStamp
            if self.server.browser_runner.current_controller.AppBuildID:
                web_data['buildid'] = self.server.browser_runner.current_controller.AppBuildID
            if self.server.browser_runner.current_controller.NameExtra:
                web_data['name_extra'] = self.server.browser_runner.current_controller.NameExtra

            raw_data = json.dumps(web_data)
            content_type = 'application/json; charset=utf-8'

            req = urllib2.Request(config.server_results_url, raw_data)
            req.add_header('Content-Type', content_type)
            req.add_header('Content-Length', len(raw_data))

            try:
                response = json.loads(urllib2.urlopen(req).read())
            except (urllib2.URLError, urllib2.HTTPError):
                print '**ERROR sending results to server:'
                traceback.print_exc()
                print
            else:
                if response['result'] == 'ok':
                    print '[%s] Results submitted to server.' % (testname)
                else:
                    print '[%s] **ERROR sending results to server: %s' % \
                        (testname, response['error'])
        self.send_response(200)
        self.end_headers()
        self.wfile.write('<html></html>')
        self.server.browser_runner.next_test()

        print "...done (POST)."

#    def log_message(self, format, *args):
#        """ Suppress log output. """
#        return


class TestRunnerHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    
    def __init__(self, server_address, browser_runner):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, TestRunnerRequestHandler)

        daemon_threads = True
        allow_reuse_address = True

        self.browser_runner = browser_runner
        self.results = collections.defaultdict(lambda: collections.defaultdict(list))

    def reset(self):
        self.results = collections.defaultdict(lambda: collections.defaultdict(list))

    def standard_web_data(self):
        return {'ip': config.local_ip, 'client': config.client}

    def handle_error(self, request, client_address):
        print '-'*40
        print 'Exception happened during processing of request from', client_address
        traceback.print_exc() # XXX But this goes to stderr!
        print '-'*40

        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_value is not None and str(exc_value).find("Errno"):
            # ignore
            return

        # must use os._exit, otherwise this won't actually exit (sys.exit is
        # implemented by throwing an exception)
        os._exit(1)

MAX_TEST_TIME = datetime.timedelta(seconds=60*15)
        
def main():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-f', '--config', dest='config_file', type='string', action='store', default=None,
                      help='config file (default speedtests.conf)')
    parser.add_option('-t', '--test', dest='tests', action='append', default=[])
    parser.add_option('--testmode', dest='testmode', action='store_true')
    parser.add_option('-n', '--noresults', dest='noresults',
                      action='store_true')
    parser.add_option('--ignore', dest='ignore', action='store_true',
                      help='instruct server to ignore results')
    parser.add_option('--client', dest='client', type='string', action='store',
                     help='override client name reported to server')
    parser.add_option('--platform', dest='platform', type='string', action='store',
                     help='override detected platform')
    parser.add_option('--port', dest='local_port', type='int', action='store',
                     help='override local_port')
    parser.add_option('--cycles', dest='cycles', type='int', default=1, action='store',
                      help='number of cycles to run, default 1, -1 to run forever')
    parser.add_option('--forever', dest='cycles', const=-1, action='store_const',
                      help='run forever')
    parser.add_option('--nap_after', dest='nap_after', type='int', action='store',
                      help='take a break after this many cycles (0=never)')
    parser.add_option('--nap_time', dest='nap_time', type='int', action='store',
                      help='duration of nap, in seconds')
    parser.add_option('--reboot_after', dest='reboot_after', type='int', action='store',
                      help='reboot device after this many cycles (0=never)')

    (options, args) = parser.parse_args()

    config.read(options.testmode, options.noresults, options.ignore, options.config_file)

    if options.client:
        config.client = options.client

    if options.local_port:
        config.local_port = options.local_port

    if not options.client and not config.get_str('speedtests', 'client'):
        print "--client must be specified on command line or in config (we don't support ip-based clients here)"
        sys.exit(errno.EINVAL)

    if options.platform:
        config.platform = options.platform

    config.nap_after = config.get_int(config.platform, 'nap_after', 0)
    config.nap_time = config.get_int(config.platform, 'nap_time', 0)
    config.reboot_after = config.get_int(config.platform, 'reboot_after', 0)

    if options.nap_after:
        config.nap_after = options.nap_after
    if options.nap_time:
        config.nap_time = options.nap_time
    if options.reboot_after:
        config.reboot_after = options.reboot_after

    def get_browser_arg():
        try:
            browser = args[1]
        except IndexError:
            print 'Specify a browser.'
            sys.exit(errno.EINVAL)
        return browser

    evt = threading.Event()
    if len(args) >= 1 and args[0] == 'archive':
        browser = get_browser_arg()
        BrowserRunner(evt).archive_current_profiles(browser)
        sys.exit(0)
    
    # start tests in specified browsers.  if none given, run all.
    queryparams = []
    queryparams.append("ip=%s" % (config.local_ip))
    queryparams.append("port=%d" % (config.local_port))
    queryparams.append("client=%s" % (urllib2.quote(config.client, '')))

    if config.testmode:
        queryparams.append('test=true')

    url_prefix = config.local_test_base_url + '/start.html?' + "&".join(queryparams)
    url_prefix += '&testUrl='
    if not options.tests:
        print 'Getting test list from server...'
        try:
            tests_url = config.server_api_url + '/testpaths/'
            print 'Getting test list from %s...' % tests_url
            options.tests = json.loads(urllib2.urlopen(tests_url).read())
        except urllib2.HTTPError, e:
            sys.stderr.write('Could not get test list: %s\n' % e)
            sys.exit(errno.EPERM)
        except urllib2.URLError, e:
            sys.stderr.write('Could not get test list: %s\n' % e.reason)
            sys.exit(e.reason.errno)

    test_urls = map(lambda x: url_prefix + urllib2.quote(x.encode("utf-8")), options.tests)

    if len(args) >= 1 and args[0] == 'load' and len(test_urls) > 1:
        test_urls = test_urls[:1]

    browsers = args

    conf_browsers = config.get_str(config.platform, "browsers")
    if browsers is None or len(browsers) == 0 and conf_browsers is not None:
        browsers = conf_browsers.split()

    br = BrowserRunner(evt, browsers, test_urls, config.platform)
    print 'Starting HTTP server...'
    trs = TestRunnerHTTPServer(('', config.local_port), br)
    server_thread = threading.Thread(target=trs.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    cycle_count = 0

    while options.cycles == -1 or cycle_count < options.cycles:
        try:
            start = datetime.datetime.now()
            print '==== Starting test cycle %d ====' % (cycle_count+1)
            br.launch_next_browser()
            while not evt.is_set():
                if br.browser_running():
                    if evt.is_set():
                        # evt may have been set while we were waiting for the lock in
                        # browser_running().
                        break
                    if br.execution_time() > MAX_TEST_TIME:
                        print 'Test has taken too long; starting next test.'
                        br.next_test()
                else:
                    print 'Browser isn\'t running!'
                    br.next_test()
                evt.wait(60)
            end = datetime.datetime.now()
            if not config.testmode:
                report = results.SpeedTestReport(trs.results)
                print
                print 'Start: %s' % start
                print 'Duration: %s' % (end - start)
                print 'Client: %s' % config.client
                print
                print report.report()
    
            print '==== Cycle done! ===='
    
            cycle_count = cycle_count + 1
    
            if config.nap_after > 0 and cycle_count % config.nap_after == 0:
                print "Napping for %d seconds..." % (config.nap_time)
                time.sleep(config.nap_time)
    
            if config.reboot_after > 0 and cycle_count % config.reboot_after == 0:
                print "Rebooting..."
                ok = createDeviceManager().reboot()
                if not ok:
                    print "WARNING: Reboot failed!"
                # Wait for the network to come back up!
                time.sleep(45)
        except:
            print "Cycle failed! Exception:"
            traceback.print_exc()
            print "Rebooting if we can on Android, otherwise just starting over..."
            if config.platform == "android":
                ok = createDeviceManager().reboot()
                if not ok:
                    print "WARNING: Reboot failed!"
                # Wait for the network to come back up!
                time.sleep(45)
        finally:
            br.reset()
            trs.reset()
            evt.clear()


    trs.shutdown()
    server_thread.join()

if __name__ == '__main__':
    main()
