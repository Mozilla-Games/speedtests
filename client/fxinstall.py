import ftplib
import re
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
    
    WIN32ZIP_RE = re.compile('firefox-.*.en-US.win32.zip')
    WIN64ZIP_RE = re.compile('firefox-.*.en-US.win64-x86_64.zip')

    def __init__(self, install_path, win64=False):
        self.install_path = install_path
        self.win64 = win64
        self.zip_files = []

    def get_install(self):
        filename = self.get_zip()
        if filename:
            self.install(filename)
        return bool(filename)

    def dir_cb(self, line):
        if self.win64:
            m = FirefoxInstaller.WIN64ZIP_RE.search(line)
        else:
            m = FirefoxInstaller.WIN32ZIP_RE.search(line)
        if m:
            self.zip_files.append(m.group(0))

    def get_zip(self):
        self.zip_files = []
        filename = ''
        ftp = ftplib.FTP('ftp.mozilla.org')
        ftp.login()
        ftp.cwd('/pub/mozilla.org/firefox/nightly/latest-trunk/')
        ftp.dir(self.dir_cb)
        if self.zip_files:
            # use natural sorting since 10 > 9
            self.zip_files.sort(key=keynat)
            filename = self.zip_files[-1]
            ftp.retrbinary('RETR %s' % filename, open(filename, 'wb').write)
        ftp.quit()
        return filename
    
    def install(self, filename):
        zip = zipfile.ZipFile(filename, 'r')
        zip.extractall(self.install_path)


if __name__ == '__main__':
    fxins = FirefoxInstaller(None)
    fxins.get_install()
