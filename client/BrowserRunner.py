import platform
import os
import sys
import threading
import traceback
import json
import base64
import uuid

from Config import config
from BrowserController import *
from AndroidBrowserControllers import *
from FirefoxBrowserControllers import *
from OtherBrowserControllers import *

class BrowserRunner(object):
    @classmethod
    def browsers_Darwin(cls):
        from Carbon import Folder, Folders
        lib_path = Folder.FSFindFolder(Folders.kUserDomain,
                                       Folders.kDomainLibraryFolderType,
                                       Folders.kDontCreateFolder).FSRefMakePath()
        app_supp_path = Folder.FSFindFolder(Folders.kUserDomain,
                                            Folders.kApplicationSupportFolderType,
                                            Folders.kDontCreateFolder).FSRefMakePath()
        os_name = 'osx'
        return [
               BrowserController(os_name, 'firefox',
                                 os.path.join(app_supp_path, 'Firefox'),
                                 '/Applications/Firefox.app/Contents/MacOS/firefox'),
               MacLatestFxBrowserController(os_name, 'nightly',
                                            os.path.join(app_supp_path, 'Firefox'),
                                            os.getenv('HOME')),
               BrowserControllerRedirFile(os_name, 'safari',
                                          os.path.join(lib_path, 'Safari'),
                                          '/Applications/Safari.app/Contents/MacOS/Safari'),
               BrowserController(os_name, 'opera',
                                 [{'path': os.path.join(app_supp_path, 'Opera'), 'archive': 'osx_app_supp.zip'},
                                  {'path': os.path.join(lib_path, 'Opera'), 'archive': 'osx_lib.zip'}],
                                 '/Applications/Opera.app/Contents/MacOS/Opera'),
               BrowserController(os_name, 'chrome',
                                 os.path.join(app_supp_path, 'Google',
                                              'Chrome'),
                               '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
               ]

    @classmethod
    def browsers_Linux(cls):
        os_name = 'linux'
        return [
               BrowserController(os_name, 'firefox', os.path.join(os.getenv('HOME'), '.mozilla', 'firefox'),
                               '/usr/bin/firefox'),
               BrowserController(os_name, 'firefox-beta', os.path.join(os.getenv('HOME'), '.mozilla', 'firefox'),
                               '/usr/bin/firefox'),
               BrowserController(os_name, 'firefox-aurora', os.path.join(os.getenv('HOME'), '.mozilla', 'firefox'),
                               '/usr/bin/firefox'),
               BrowserController(os_name, 'firefox-nightly', os.path.join(os.getenv('HOME'), '.mozilla', 'firefox'),
                               '/usr/bin/firefox'),
               BrowserController(os_name, 'chrome', os.path.join(os.getenv('HOME'), '.config', 'google-chrome'),
                               '/usr/bin/google-chrome'),
               #LinuxLatestTinderboxFxBrowserController(os_name, 'tinderbox', os.path.join(os.getenv('HOME'), '.mozilla'), "/tmp", "mozilla-central")
               #LinuxLatestFxBrowserController(os_name, 'nightly', os.path.join(os.getenv('HOME'), '.mozilla', 'firefox'), '/tmp'),
               ]

    @classmethod
    def browsers_Windows(cls):
        os_name = 'windows'
        user_profile = os.getenv('USERPROFILE')
        app_data = os.getenv('APPDATA')
        local_app_data = os.getenv('LOCALAPPDATA')
        program_files = os.getenv('PROGRAMFILES')

        # try to find Chrome
        chromepath = os.path.join(local_app_data, 'Google\\Chrome\\Application\\chrome.exe')
        if not os.path.exists(chromepath):
            chromepath = os.path.join(user_profile, 'Local Settings\\Application Data\\Google\\Chrome\\Application\\chrome.exe')
        if not os.path.exists(chromepath):
            chromepath = os.path.join(program_files, 'Google\\Chrome\\Application\\chrome.exe')
        # if chromepath still isn't valid that's fine, it'll just get disabled in BrowserController

        return [
               BrowserController(os_name, 'firefox',
                               [{'path': os.path.join(app_data, 'Mozilla\\Firefox'), 'archive': 'windows.zip'}],
                               os.path.join(program_files, 'Mozilla Firefox\\firefox.exe')),
               WinLatestFxBrowserController(os_name, 'nightly',
                               [{'path': os.path.join(app_data, 'Mozilla\\Firefox'), 'archive': 'windows.zip'}], user_profile),
               WinLatestTinderboxFxBrowserController(os_name, 'tinderbox',
                                                     [{'path': os.path.join(app_data, 'Mozilla\\Firefox'), 'archive': 'windows.zip'}],
                                                     os.getenv('TEMP'), "mozilla-central"),
               BrowserController(os_name, 'chrome',
                                 [{'path': os.path.join(local_app_data, 'Google\\Chrome\\User Data'), 'archive': 'windows.zip'}],
                                 chromepath)

               # don't care about these
               # BrowserController(os_name, 'safari',
               #                [{'path': os.path.join(local_app_data, 'Apple Computer\\Safari'), 'archive': 'windows\\local.zip'},
               #                 {'path': os.path.join(app_data, 'Apple Computer\\Safari'), 'archive': 'windows\\roaming.zip'}],
               #                 os.path.join(program_files, 'Safari\\Safari.exe')),
               # BrowserController(os_name, 'opera',
               #                [{'path': os.path.join(local_app_data, 'Opera\\Opera'), 'archive': 'windows\\local.zip'},
               #                 {'path': os.path.join(app_data, 'Opera\\Opera'), 'archive': 'windows\\roaming.zip'}],
               #                os.path.join(program_files, 'Opera\\opera.exe')),
               # IEController(os_name, 'internet explorer', os.path.join(program_files, 'Internet Explorer\\iexplore.exe')),
               ]

    @classmethod
    def browsers_Android(cls):
        os_name = 'android'
        browsers = [
            AndroidFirefoxBrowserController(os_name, 'firefox', package='org.mozilla.firefox'),
            AndroidFirefoxBrowserController(os_name, 'firefox-beta', package='org.mozilla.firefox_beta'),
            AndroidFirefoxBrowserController(os_name, 'firefox-aurora', package='org.mozilla.fennec_aurora'),
            AndroidFirefoxBrowserController(os_name, 'firefox-nightly', package='org.mozilla.fennec'),
            #AndroidLatestFxAdbBrowserController(os_name, 'nightly'),
            #AndroidTinderboxFxBrowserController(os_name, 'tinderbox'),
            #AndroidBrowserController(os_name, 'browser', 'com.google.android.browser'),
            AndroidChromeBrowserController(os_name, 'chrome', 'com.android.chrome'),
            AndroidChromeBrowserController(os_name, 'chrome-beta', 'com.chrome.beta'),
            #AndroidOperaBrowserController(os_name, 'opera')
            ]
        if config.include_dev_builds:
            browsers.append(AndroidFirefoxBrowserController(os_name, 'fennec_' + os.getenv('USER'), package='org.mozilla.fennec_' + os.getenv('USER')))
        return browsers

    @classmethod
    def browsers_by_os(cls, os_str):
        if os_str == 'Darwin':
            return BrowserRunner.browsers_Darwin()

        if os_str == 'Linux':
            return BrowserRunner.browsers_Linux()

        if os_str == 'Windows':
            return BrowserRunner.browsers_Windows()

        if os_str == 'android':
            return BrowserRunner.browsers_Android()

        raise Exception("Unrecognized platform '%s'" % (os_str))

    class BrowserControllerIter(object):
        def __init__(self, controllers, browser_names=[]):
            self.controllers = controllers
            self.browser_names = browser_names
            self.iter = iter(self.controllers)

        def __iter__(self):
            return self

        def next(self):
            while True:
                try:
                    n = self.iter.next()
                except StopIteration:
                    raise
                if not self.browser_names or n.browser_name in self.browser_names:
                    return n

    class TestURLIter(object):
        def __init__(self, tests, client, controller, baseconfig):
            self.config = baseconfig.copy()
            self.config['client'] = client
            self.config['browser'] = controller.browser_name
            if controller.AppSourceStamp:
                self.config['browserSourceStamp'] = controller.AppSourceStamp
            if controller.AppBuildID:
                self.config['browserBuildID'] = controller.AppBuildID
            if controller.NameExtra:
                self.config['browserNameExtra'] = controller.NameExtra

            #print json.dumps(self.config)

            self.configstr = base64.b64encode(json.dumps(self.config))

            self.test_iter = iter(tests)

        def __iter__(self):
            return self

        def next(self):
            while True:
                try:
                    test = self.test_iter.next()
                except StopIteration:
                    raise

                url = config.test_base_url + "/" + test + "/index.html"
# TODO: figure out a method for making this optional, it fails when we are loading from the local storage on android
#                if not test.endswith("/"):
#                    url += "/"

                if '?' in url:
                    url += "&_benchconfig=" + self.configstr
                else:
                    url = url + "?_benchconfig=" + self.configstr
                url += "&_bench_name=" + test

                return url

    def __init__(self, evt, browser_names, tests, testconfig):
        self.evt = evt
        self.tests = tests
        self.testconfig = testconfig
        self.browser_names = browser_names

        platform = testconfig['platform']

        try:
            self.browsers = BrowserRunner.browsers_by_os(platform)
        except KeyError:
            sys.stderr.write('Unknown platform "%s".\n' % platform)
            sys.exit(errno.EOPNOTSUPP)

        self.current_controller = None
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.lock.acquire()
        if self.current_controller:
            self.current_controller.terminate()
        self.current_controller = None
        self.browser_iter = BrowserRunner.BrowserControllerIter(self.browsers, self.browser_names)
        self.lock.release()

    def find_browser(self, browsername):
        for b in self.browsers:
            if b.browser_name == browsername:
                return b
        print 'Unknown browser "%s".' % browsername
        return None

    def archive_current_profiles(self, browsername):
        b = self.find_browser(browsername)
        if b:
            b.archive_current_profiles()

    def launch(self, browsername, url):
        b = self.find_browser(browsername)
        if b:
            b.launch(url)

    def browser_running(self):
        self.lock.acquire()
        running = self.current_controller.running()
        self.lock.release()
        return running

    def execution_time(self):
        self.lock.acquire()
        t = self.current_controller.execution_time()
        self.lock.release()
        return t

    def browser_name(self):
        self.lock.acquire()
        browser_name = self.current_controller.browser_name
        self.lock.release()
        return browser_name

    def get_current_test(self):
        return self.current_test_url

    def get_current_test_token(self):
        return self.current_test_token

    def next_test(self):
        if not self.current_controller:
            self.launch_next_browser()

        need_to_launch = False

        self.lock.acquire()
        try:
            if self.current_controller.running():
                self.current_controller.terminate()

            url = self.test_url_iter.next()
            token = str(uuid.uuid4())
            run_uuid = "RUN-" + str(uuid.uuid4())

            self.current_test_url = url + "&_benchtoken=" + token + "&_run_uuid=" + run_uuid
            self.current_test_token = token

            self.current_controller.launch(self.current_test_url)
        except StopIteration:
            need_to_launch = True

        self.lock.release()

        if need_to_launch:
            self.launch_next_browser()

    def launch_next_browser(self):
        self.lock.acquire()
        if self.current_controller:
            #print 'Closing browser...'
            self.current_controller.terminate()
            print '%s test running time: %s' % (self.current_controller.browser_name, self.current_controller.execution_time())

        while True:
            # Try to grab the next browser to test; if none left,
            # we're done.
            try:
                if self.current_controller:
                    print '* %s: done.\n' % self.current_controller.browser_name

                self.current_controller = self.browser_iter.next()
            except StopIteration:
                self.evt.set()
                self.lock.release()
                return

            try:
                browser_name = self.current_controller.browser_name
                print '* %s: initializing...' % browser_name

                self.current_test_url = None
                self.test_url_iter = BrowserRunner.TestURLIter(self.tests,
                                                               config.client,
                                                               self.current_controller,
                                                               self.testconfig)

                if not self.current_controller.init_browser():
                    print '! Failed to init %s, skipping...' % browser_name
                    continue

                if not self.current_controller.browser_exists():
                    print "! Browser %s doesn't exist, skipping..." % browser_name
                    continue

                print '* %s: launching...' % browser_name
                self.lock.release()
                return

            except:
                print 'Failed to launch or initialize browser.'
                traceback.print_exc()

        self.lock.release()
