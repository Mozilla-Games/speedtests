# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import SocketServer
import BaseHTTPServer
import base64
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
import urlparse
import zipfile
import StringIO

from Config import config
from BrowserRunner import *
from BrowserController import *
import results


#
# The RequestHandler here has one job -- to get a "test done" post from
# the test and to continue on to the next test.  It doesn't forward --
# tests themselves should be loaded from a real HTTP server.
#
# Note that this communication channel could be turned into something else,
# for example WebSockets based, but using POST/GET is the simplest and
# most widely supported.
#
# Test invocation goes like this:
#
# - Framework invokes browser with one-time test URL, which hits this request
#   handler and redirects to the actual test.  This lets the framework rewrite
#   also rewrite the test URL based on the user agent, if needed.
# - Test URL executes.  When it finishes, it does two XHR requests:
# - One XHR to the results server (passed in query params to test in special _speedtests parameter)
# - One XHR to the speedtests framework (handled below); this indicates that the test is done, and that
#   the framework can continue to the next test.
#
# This is mainly so that we can get notified that the test was actually loaded.
class TestRunnerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    
    def do_GET(self):
        print "Handling GET '%s'..." % (self.path)

        o = urlparse.urlparse(self.path)
        q = urlparse.parse_qs(o.query)

        if o.path != "/submit-result":
            self.send_error(404)
            self.end_headers()
            return

        target = q['target'][0]
        data = json.loads(base64.b64decode(q['data'][0]))
        #print target
        #print data

        self.send_response(200)
        self.send_header("Content-type", "text/javascript")
        self.end_headers()

        self.wfile.write('SpeedTests["%s" + "Done"] = true;' % (target))

            # if self.server.browser_runner.current_controller.AppSourceStamp:
            #     web_data['sourcestamp'] = self.server.browser_runner.current_controller.AppSourceStamp
            # if self.server.browser_runner.current_controller.AppBuildID:
            #     web_data['buildid'] = self.server.browser_runner.current_controller.AppBuildID
            # if self.server.browser_runner.current_controller.NameExtra:
            #     web_data['name_extra'] = self.server.browser_runner.current_controller.NameExtra

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

    config.read(options.noresults, options.ignore, options.config_file)

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

    # create a configuration object to pass to the tests
    testconfig = dict()
    testconfig["clientName"] = config.client
    testconfig["runnerServer"] = "http://%s:%d/submit-result" % (config.local_ip, config.local_port)
    testconfig["platform"] = config.platform
    if not options.noresults:
        testconfig["resultServer"] = config.results_server

    test_extra_params = "_benchconfig=" + base64.b64encode(json.dumps(testconfig))

    if not options.tests:
        print 'Getting test list from server...'
        try:
            tests_url = config.test_base_url + '/testpaths/?' + test_extra_params
            print 'Getting test list from %s...' % tests_url
            options.tests = json.loads(urllib2.urlopen(tests_url).read())
        except urllib2.HTTPError, e:
            sys.stderr.write('Could not get test list: %s\n' % e)
            sys.exit(errno.EPERM)
        except urllib2.URLError, e:
            sys.stderr.write('Could not get test list: %s\n' % e.reason)
            sys.exit(e.reason.errno)

    test_urls = []
    for test in options.tests:
        url = config.test_base_url + "/" + test
        if '?' in url:
            url = url + "&" + test_extra_params
        else:
            url = url + "?" + test_extra_params
        test_urls.append(url)
                        
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
