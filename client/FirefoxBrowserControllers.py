import shutil
import urllib
import zipfile

from BrowserController import *
from AndroidBrowserControllers import *
from get_latest import GetLatestTinderbox
import fxinstall

class LatestFxBrowserController(BrowserController):
    
    """ Specialization to download latest nightly before launching. """

    # FIXME: if we fail to contact ftp.mozilla.org, recover gracefully
    
    INSTALL_SUBDIR = 'speedtests_firefox_nightly'

    # override these
    ARCHIVE_FX_PATH = ''
    INSTALLER_CLASS = None

    def __init__(self, os_name, browser_name, profiles, base_install_dir):
        self.base_install_dir = os.path.join(base_install_dir, config.client)
        cmd = os.path.join(self.base_install_dir,
                           LatestFxBrowserController.INSTALL_SUBDIR,
                           self.ARCHIVE_FX_PATH)
        super(LatestFxBrowserController, self).__init__(os_name, browser_name, profiles, cmd)

    def init_browser(self):
        install_path = os.path.join(self.base_install_dir,
                                    LatestFxBrowserController.INSTALL_SUBDIR)
        installer = self.INSTALLER_CLASS(install_path, config.sixtyfour_bit)
        print 'Getting firefox nightly...'
        try:
            if not installer.get_install():
                print 'Failed to get firefox nightly.'
                return False
        except:
            print 'Failed to get firefox nightly.'
            if config.verbose:
                traceback.print_exc()
            return False

        try:
            self.parse_app_ini(os.path.join(install_path, 'firefox', 'application.ini'))
        except:
            pass
        return True

class LatestTinderboxFxBrowserController(BrowserController):
    
    """ Specialization to download latest tinderbox build before launching. """

    # FIXME: if we fail to contact ftp.mozilla.org, recover gracefully
    
    INSTALL_SUBDIR = 'speedtests_firefox_tb'

    # override these
    ARCHIVE_FX_PATH = None
    PLATFORM = None

    # maybe override these
    BUILDTYPE = None   # "debug", "pgo", ...

    # filled out from application.ini
    AppVersion = None
    AppBuildID = None
    AppSourceRepository = None
    AppSourceStamp = None

    last_download_url = None

    def __init__(self, os_name, browser_name, profiles, base_install_dir, branch='mozilla-central'):
        self.base_install_dir = os.path.join(base_install_dir, config.client)
        self.branch = branch
        cmd = os.path.join(self.base_install_dir,
                           self.INSTALL_SUBDIR,
                           self.ARCHIVE_FX_PATH)
        super(LatestTinderboxFxBrowserController, self).__init__(os_name, browser_name, profiles, cmd)

    def init_browser(self):
        install_path = os.path.join(self.base_install_dir, self.INSTALL_SUBDIR)
        latest = GetLatestTinderbox(self.branch, self.PLATFORM, buildtype=self.BUILDTYPE, app='firefox', app_short='firefox')

        try:
            latest_url = latest.latest_build_url()
            basename = latest_url[latest_url.rfind("/")+1:]
        except:
            if config.verbose:
                traceback.print_exc()
            return False

        try:
            if self.last_download_url is None:
                shutil.rmtree(install_path)
                os.makedirs(install_path)
        except:
            pass

        if not os.path.exists(install_path):
            print "! failed to create temp dir path: %s" % install_path
            return False

        destfile = os.path.join(install_path, basename)

        try:
            if latest_url == self.last_download_url and os.path.exists(destfile):
                print "Skipping fetching " + latest_url + ", already have it"
            else:
                print "Fetching " + latest_url + "..."
                urllib.urlretrieve(latest_url, destfile)
                self.last_download_url = latest_url
        except:
            print 'Failed to get latest tinderbox build'
            if config.verbose:
                traceback.print_exc()
            self.last_download_url = None
            return False

        appini = self.prepare_archived_build(install_path, destfile)
        if appini is None:
            print 'Failed to get application.ini!'
            return False

        self.parse_app_ini(appini)
        return True

class LinuxLatestTinderboxFxBrowserController(LatestTinderboxFxBrowserController):
    ARCHIVE_FX_PATH = 'firefox/firefox'
    PLATFORM = 'linux'
    BUILDTYPE = 'pgo'

    def __init__(self, os_name, browser_name, profiles, base_install_dir, branch='mozilla-central'):
        super(LinuxLatestTinderboxFxBrowserController, self).__init__(os_name, browser_name, profiles, base_install_dir, branch)

    def prepare_archived_build(self, install_path, buildpath):
        # on linux, this is a bz2 file
        try:
            subprocess.check_call("cd '" + install_path + "' && tar xjf '" + buildpath + "'", shell=True)
            return os.path.join(install_path, "firefox", "application.ini")
        except Exception as e:
            print "Failed to unpack:"
            print e
            return None

class WinLatestTinderboxFxBrowserController(LatestTinderboxFxBrowserController):
    ARCHIVE_FX_PATH = 'firefox\\firefox.exe'
    PLATFORM = 'win32'
    BUILDTYPE = 'pgo'

    def __init__(self, os_name, browser_name, profiles, base_install_dir, branch='mozilla-central'):
        super(WinLatestTinderboxFxBrowserController, self).__init__(os_name, browser_name, profiles, base_install_dir, branch)

    def prepare_archived_build(self, install_path, buildpath):
        # on windows, this is a zip file
        cwd = os.getcwd()
        try:
            fn = os.path.basename(buildpath)
            os.chdir(install_path)
            print "chdir to " + install_path + " cwd now " + os.getcwd()
            subprocess.check_call("unzip -q \"%s\"" % (fn), shell=True)
            return os.path.join(install_path, "firefox", "application.ini")
        except Exception as e:
            print "Failed to unpack:"
            print e
            return None
        finally:
            os.chdir(cwd)

class AndroidTinderboxFxBrowserController(AndroidFirefoxBrowserController):
    INSTALL_SUBDIR = 'speedtests_fennec_tb'
    last_download_url = None

    def __init__(self, os_name, browser_name, branch='mozilla-central'):
        # explicitly not using super()
        AndroidFirefoxBrowserController.__init__(self, os_name, browser_name, package='org.mozilla.fennec')

        # stuff from LatestTinderboxFxBrowserController.__init__
        self.base_install_dir = os.path.join("/tmp", config.client)
        self.branch = branch

    def init_browser(self):
        install_path = os.path.join(self.base_install_dir, self.INSTALL_SUBDIR)

        try:
            if self.last_download_url is None:
                shutil.rmtree(install_path)
                os.makedirs(install_path)
        except:
            pass

        if not os.path.exists(install_path):
            print "! failed to create temp dir path: %s" % install_path
            return False

        latest = GetLatestTinderbox(self.branch, "android", app='mobile', app_short='fennec')
        latest_url = latest.latest_build_url()
        basename = latest_url[latest_url.rfind("/")+1:]

        apkpath = os.path.join(install_path, basename)

        try:
            if latest_url == self.last_download_url and os.path.exists(apkpath):
                print "Skipping fetching " + latest_url + ", already have it"
            else:
                print "Fetching " + latest_url + "..."
                urllib.urlretrieve(latest_url, apkpath)
                self.last_download_url = latest_url
        except Exception as e:
            print 'Failed to get latest tinderbox build'
            if config.verbose:
                traceback.print_exc()
            self.last_download_url = None
            return False

        # pull out app.ini and parse it
        zip = zipfile.ZipFile(apkpath, 'r')
        zip.extract("application.ini", install_path)
        self.parse_app_ini(os.path.join(install_path, "application.ini"))

        # now install the apk
        return self.dm.installLocalApp(apkpath)

class LinuxLatestFxBrowserController(LatestFxBrowserController):

    ARCHIVE_FX_PATH = 'firefox/firefox'
    INSTALLER_CLASS = fxinstall.FirefoxLinuxInstaller

class WinLatestFxBrowserController(LatestFxBrowserController):

    ARCHIVE_FX_PATH = 'firefox\\firefox.exe'
    INSTALLER_CLASS = fxinstall.FirefoxWinInstaller

class MacLatestFxBrowserController(LatestFxBrowserController):

    ARCHIVE_FX_PATH = 'FirefoxNightly.app/Contents/MacOS/firefox'
    INSTALLER_CLASS = fxinstall.FirefoxMacInstaller

