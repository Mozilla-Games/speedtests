# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import ftplib
import os
import re
import shutil
import sys
import zipfile

# taken from one of the comments at
#   http://code.activestate.com/recipes/285264-natural-string-sorting/
def keynat(string):
    r'''A natural sort helper function for sort() and sorted()
    without using regular expression.

    >>> items = ('Z', 'a', '10', '1', '9')
    >>> sorted(items)
    ['1', '10', '9', 'Z', 'a']
    >>> sorted(items, key=keynat)
    ['1', '9', '10', 'Z', 'a']
    '''
    r = []
    for c in string:
        try:
            c = int(c)
            try: r[-1] = r[-1] * 10 + c
            except: r.append(c)
        except:
            r.append(c)
    return r


class FirefoxInstaller(object):

    ARCHIVE_32_BIT_RE = None
    ARCHIVE_64_BIT_RE = None
    FTP_PATH = '/pub/mozilla.org/firefox/nightly/latest-trunk/'

    def __init__(self, install_path, sixtyfour_bit=False):
        self.install_path = install_path
        self.sixtyfour_bit = sixtyfour_bit
        self.archive_files = []

    def get_install(self):
        print 'Fetching archive...'
        filename = self.get_archive()
        if filename:
            print 'Removing old installation...'
            shutil.rmtree(self.install_path, ignore_errors=True)
            print 'Installing nightly...'
            os.makedirs(self.install_path)
            self.install(filename)
            print 'Done installing nightly.'
        else:
            print 'Archive not found!'
        return bool(filename)

    def dir_cb(self, line):
        m = None
        if self.sixtyfour_bit and self.ARCHIVE_64_BIT_RE:
            m = self.ARCHIVE_64_BIT_RE.search(line)
        elif self.ARCHIVE_32_BIT_RE:
            m = self.ARCHIVE_32_BIT_RE.search(line)
        if m:
            self.archive_files.append(m.group(0))

    def get_archive(self):
        self.archive_files = []
        filename = ''
        ftp = ftplib.FTP('ftp.mozilla.org')
        ftp.login()
        ftp.cwd(self.FTP_PATH)
        ftp.dir(self.dir_cb)
        if self.archive_files:
            # use natural sorting since 10 > 9
            self.archive_files.sort(key=keynat)
            filename = self.archive_files[-1]
            ftp.retrbinary('RETR %s' % filename, open(filename, 'wb').write)
        ftp.quit()
        return filename

    def install(self, filename):
        pass


class FirefoxWinInstaller(FirefoxInstaller):
    
    ARCHIVE_32_BIT_RE = re.compile('firefox-.*.en-US.win32.zip')
    ARCHIVE_64_BIT_RE = re.compile('firefox-.*.en-US.win64-x86_64.zip')
    
    def install(self, filename):
        zip = zipfile.ZipFile(filename, 'r')
        zip.extractall(self.install_path)

class FirefoxLinuxInstaller(FirefoxInstaller):
    
    ARCHIVE_32_BIT_RE = re.compile('firefox-.*.en-US.linux-i686.tar.bz2')
    
    def install(self, filename):
        os.system('tar xjCf "%s" "%s"' % (self.install_path, filename))

class FirefoxMacInstaller(FirefoxInstaller):

    ARCHIVE_32_BIT_RE = re.compile('firefox-.*.en-US.mac.dmg')

    def install(self, filename):
        print 'Mounting volume...'
        os.system('hdid %s' % filename)
        print 'Copying...'
        target_dir = os.path.join(self.install_path, 'Nightly.app')
        shutil.copytree('/Volumes/Nightly/Nightly.app/', target_dir)
        print 'Unmounting...'
        os.system('umount /Volumes/Nightly')


if __name__ == '__main__':
    import errno
    import platform
    from optparse import OptionParser
    install_classes = { 'Windows': FirefoxWinInstaller,
                        'Darwin': FirefoxMacInstaller }
    defaults = { 'Windows': { 'base_install': os.getenv('USERPROFILE') },
                 'Darwin': { 'base_install': os.getenv('HOME') } }
    parser = OptionParser()
    parser.add_option('-d', '--dir', dest='base_install', default=None,
                      help='base installation directory')
    parser.add_option('-p', '--platform', dest='platform', default=None,
                      help='target Firefox platform (\'Darwin\', \'Linux\')')
    (options, args) = parser.parse_args()
    fxins = None
    if options.platform is None:
        options.platform = platform.system()
    if not options.platform in install_classes:
        print 'No installer for %s.' % options.platform
        sys.exit(errno.EINVAL)

    if options.base_install is None:
        options.base_install = defaults.get(platform.system(), None)
    if options.base_install is None:
        print 'No base install path given and no default defined for ' + \
              'platform %s.' % platform.system()
        sys.exit(errno.EINVAL)

    fxins = install_classes[options.platform](os.path.join(options.base_install,
                                                           'speedtests'))
    fxins.get_install()
