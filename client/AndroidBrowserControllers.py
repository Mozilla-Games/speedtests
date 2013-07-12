import traceback
import re
	
from Config import config
from BrowserController import *
from mozdevice import DroidADB, DroidSUT, DroidConnectByHWID

def createDeviceManager(**kwargs):
    hwid = os.getenv("DM_HWID")
    dm = None
    if hwid is None:
        dm = DroidADB(skipRoot=True, **kwargs)
    else:
        dm = DroidConnectByHWID(hwid, skipRoot=True, **kwargs)
    if dm is None:
        raise Exception("Failed to create device manager!")
    # do something to make sure it's alive
    dm.getInfo("id")
    return dm


class AndroidBrowserController(BrowserController):
    def __init__(self, os_name, browser_name, package='org.mozilla.fennec', activity='.App'):
        super(AndroidBrowserController, self).__init__(os_name, browser_name, "default", None)
        self.browserPackage = config.get_str('android', browser_name + '_package', package)
        self.browserActivity = config.get_str('android', browser_name + '_activity', activity)
        self.dm = createDeviceManager(packageName=package)

        self.remoteProfile = "%s/profile" % self.dm.getDeviceRoot()
        #TODO: pull this in from the conf file, we might want to specify something custom
        self.localProfile = "android_profile"

    def cmd_line(self, url):
        pass

    def init_browser(self):
        return True

    def browser_exists(self):
        # XXX fixme to check
        return True

    def get_profile_archive_path(self, profile):
        raise Exception("Can't get profile archive for Android fennec browser")

    def archive_current_profiles(self):
        raise Exception("Can't get profile archive for Android fennec browser")

    def copy_profiles(self):
        try:
            self.dm.pushDir(self.localProfile, self.remoteProfile)
        except:
            return False
        return True

    def copy_tests(self):
        if re.match('file:\/\/\/.*', config.test_base_url):
            try:
                self.dm.pushDir(os.path.join('..', 'html'), '/mnt/sdcard/html')
            except:
                return False
        return True

    def launch(self, url=None):
        if not self.copy_profiles():
            print "ERROR: unable to copy profile, terminating test"
            return False

        if not self.copy_tests():
            print "ERROR: unable to copy the tests to the local device, terminating test"
            return False

        try:
            # simulate a press of the HOME button, to wake screen up if necessary
            self.dm.shell(["input", "keyevent", "3"], None)

            if url is None:
                url = "about:blank"
            
            #print "ADB Launch command line: %s" % (cmdline)
            self.launch_time = datetime.datetime.now()
            extras = {}
            extras['args'] = ' '.join(['-profile', self.remoteProfile])
            return self.dm.launchApplication(self.browserPackage, self.browserActivity, "android.intent.action.VIEW", extras=extras, url=url)
        except:
            traceback.print_exc()
            return False

    def getBrowserPid(self):
        result = self.dm.processExist(self.browserPackage)
        #print "getBrowserPid -> ", str(result)
        if result is not None:
            return result
        return -1

    def running(self):
        return self.getBrowserPid() > 0

    def terminate(self):
        if config.verbose:
            print "controller.terminate(), trying.."
        pid = self.getBrowserPid()
        if pid < 0:
            return

        # the killProcess implementaiton is not ideal; requires root or run-as
        self.dm.killProcess(self.browserPackage, forceKill=True)
        if self.getBrowserPid() > 0:
            self.dm.killProcess(self.browserPackage)
        if self.getBrowserPid() > 0:
            self.dm.shell(["kill", pid], None, root=True)
        if self.getBrowserPid() > 0:
            self.dm.shell(["kill", "-9", pid], None, root=True)

        if False:
            needRoot = False
            if type(self.dm) is DroidSUT:
                needRoot = True

            out = StringIO.StringIO()
            self.dm.shell(["am", "force-stop", self.browserPackage], out, root=needRoot)
            print "force-stop:", out.getvalue()
            time.sleep(1)
            out = StringIO.StringIO()
            self.dm.shell(["am", "kill", self.browserPackage], None, root=needRoot)
            print "kill:", out.getvalue()

        pid = self.getBrowserPid()
        count = 0
        while pid > 0:
            time.sleep(2)
            pid = self.getBrowserPid()
            count += 1
            if count == 20:
                raise Exception("Waited too long for browser to die!")
        self.clean_up()

class AndroidFirefoxBrowserController(AndroidBrowserController):
    def __init__(self, os_name, browser_name, package='org.mozilla.firefox', activity='.App'):
        super(AndroidFirefoxBrowserController, self).__init__(os_name, browser_name, package, activity)

    def clean_up(self):
        self.dm.shell(["rm", "/data/data/" + self.browserPackage + "/files/mozilla/*.default/session*"], None, root=True)

class AndroidChromeBrowserController(AndroidBrowserController):
    def __init__(self, os_name, browser_name, package='com.android.chrome', activity='com.google.android.apps.chrome.Main'):
        super(AndroidChromeBrowserController, self).__init__(os_name, browser_name, package, activity)

    def clean_up(self):
        self.dm.shell(["rm", "/data/data/" + self.browserPackage + "/files/tab*"], None, root=True)
