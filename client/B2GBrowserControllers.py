import traceback
import re
import subprocess
import tempfile

from Config import config
from BrowserController import *
from mozdevice import DroidADB, DroidSUT, DroidConnectByHWID

import gaiatest
from gaiatest.apps.browser.app import Browser
from marionette import Marionette


def startMarionette():
    # FW port for ADB via USB
    return_code = subprocess.call(["adb root"], shell=True)
    if return_code:
        raise Exception("Failed to start adb in root mode. Ensure device is attached to USB.")
    return_code = subprocess.call(["adb forward tcp:2828 tcp:2828"], shell=True)
    if return_code:
        raise Exception("Failed to connect to device via ADB; ensure device is attached to USB.")
    # Start Marionette
    marionette = Marionette(host='localhost', port=2828)
    
    marionette.start_session()
    marionette.set_script_timeout(60000)
    return marionette

class B2GBrowserController(BrowserController):

    _awesome_bar_locator = ('id', 'url-input')

    def __init__(self, os_name, browser_name, package=None, activity=None):
        super(B2GBrowserController, self).__init__(os_name, browser_name, None, None)
        # Start Marionette
        self.marionette = startMarionette()
        self.dm = self.device = gaiatest.GaiaDevice(self.marionette)
        # Set the required Firefox OS Browser App prefs
        self.set_ffox_browser_prefs()
        # Restart b2g process on device
        print 'Restarting b2g process...'
        self.dm.restart_b2g()
        time.sleep(10)

    def set_ffox_browser_prefs(self):
        print "Setting FirefoxOS Browser prefs..."
        # Find and pull Firefox OS prefs file from device
        return_code = subprocess.call(['adb pull $(adb shell echo -n "/data/b2g/mozilla/*.default")/prefs.js prefs.js'], shell=True)
        if return_code:
            raise Exception("Failed to pull prefs file from device.")
        # Add required prefs so long-running script won't timeout the browser
        return_code = subprocess.call(["echo 'user_pref(\"dom.max_script_run_time\", 0);' >> prefs.js"], shell=True)
        if return_code:
            raise Exception("Failed to append pref to local prefs file.")
        return_code = subprocess.call(["echo 'user_pref(\"dom.script_run_time\", 0);' >> prefs.js"], shell=True)
        if return_code:
            raise Exception("Failed to append pref to local prefs file.")
        # Now push prefs back to the Firefox OS device; note, b2g process must be restarted at somepoint afterwards
        return_code = subprocess.call(['adb push prefs.js $(adb shell echo -n "/data/b2g/mozilla/*.default")/prefs.js'], shell=True)
        if return_code:
            raise Exception("Failed to push prefs file back to device.")
        # Now remove the temp file 'prefs.js' from the local dir
        return_code = subprocess.call(['rm prefs.js'], shell=True)
        if return_code:
            raise Exception("Failed to delete local 'prefs.js' temp file.")

    def cmd_line(self, url):
        pass

    def init_browser(self):
        return True

    def browser_exists(self):
        # XXX fixme to check
        return True

    def get_profile_archive_path(self, profile):
        #raise Exception("Can't get profile archive for Android fennec browser")
        pass

    def archive_current_profiles(self):
        #raise Exception("Can't get profile archive for Android fennec browser")
        pass

    def copy_profiles(self):
        try:
            self.dm.pushDir(self.localProfile, self.remoteProfile)
        except:
            return False
        return True

    def get_git_revision(self):
        gitrev = subprocess.check_output("git show HEAD | grep '^commit'",
                                         shell=True)
        rev = gitrev.strip().split(' ')
        return rev[1]

    def device_has_tests(self):
        htmlRev = self.get_git_revision()
        print "Local REV: %s" % (htmlRev,)
        remoteRev = None
        if 'html.rev' in self.dm.listFiles('/mnt/sdcard'):
            data = self.dm.pullFile('/mnt/sdcard/html.rev')
            dataLines = [line.strip() for line in data.split('\n')]
            if len(dataLines) > 0:
                remoteRev = dataLines[0]
                print "Remote REV: %s" % (remoteRev,)
        return htmlRev == remoteRev

    def mark_device_has_tests(self):
        htmlRev = self.get_git_revision()
        f = tempfile.NamedTemporaryFile()
        localName = f.name
        f.write(htmlRev)
        f.flush()
        self.dm.pushFile(localName, "/mnt/sdcard/html.rev")
        f.close()

    def copy_tests(self):
        if re.match('file:\/\/\/.*', config.test_base_url):
            if not self.device_has_tests():
                try:
                    self.dm.pushDir(os.path.join('..', 'html'),
                                    '/mnt/sdcard/html')
                    self.mark_device_has_tests()
                except:
                    return False
        return True

    def launch(self, url=None):
        # Unlock the screen
        gaiatest.LockScreen(self.marionette).unlock()

        # Ensure browser app is installed
        if not gaiatest.GaiaApps(self.marionette).is_app_installed("Browser"):
            raise Exception("Browser app is not installed, cannot continue.")

        # Kill any running apps; after b2g restart it is possible the first time use app comes up
        gaiatest.GaiaApps(self.marionette).kill_all()
        time.sleep(2)

        # Ensure are on homescreen (should be after kill all above anyway)
        self.marionette.execute_script('window.wrappedJSObject.dispatchEvent(new Event("home"));')

        # Start browser app
        self.browser = Browser(self.marionette)
        self.browser.launch()

        # Verify browser app is now running
        if not self.running():
            raise Exception("Browser app failed to start. Cannot continue.")

        # Wait time for browser app to 'settle'
        time.sleep(30)

        # Launch the test by navigating to the URL
        url = url.replace('&', '\\&')
        self.browser.switch_to_chrome()
        #print url
        self.launch_time = datetime.datetime.now()
        self.marionette.execute_script("return window.wrappedJSObject.Browser.navigate('%s');" %url)
        return self.running()

    def getBrowserPid(self):
        result = self.dm.processExist(self.browserPackage)
        #print "getBrowserPid -> ", str(result)
        if result is not None:
            return result
        return -1

    def running(self):
        self.marionette.switch_to_frame()
    	apps = gaiatest.GaiaApps(self.marionette).runningApps()
    	currently_running_apps = ''.join(apps)
        return "browser" in currently_running_apps

    def terminate(self):
        # Kill all apps running on Firefox OS
        gaiatest.GaiaApps(self.marionette).kill_all()
        time.sleep(10)
        self.clean_up()

class B2GFirefoxBrowserController(B2GBrowserController):
    def __init__(self, os_name, browser_name, package=None, activity=None):
        super(B2GFirefoxBrowserController, self).__init__(os_name, browser_name, package, activity)

    def clean_up(self):
        pass
        #self.dm.shell(["rm", "/data/data/" + self.browserPackage + "/files/mozilla/*.default/session*"], None, root=True)
        # Clear browser cache on Firefox OS device
        #print "<TO-DO> Blow-away Firefox OS app cache here?"
        #return_code = subprocess.call(["adb shell rm <cache path>"], shell=True)
        #if return_code:
        #    raise Exception("Failed to connect to clear Browser app cache on the Firefox OS device.")
