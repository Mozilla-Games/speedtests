#!/usr/bin/python

import sys
import argparse
import os
import os.path
import re
import gdata.data
import gdata.docs.client
import gdata.docs.data
import gdata.docs.service
import gdata.sample_util
import ConfigParser

class DefaultConfigParser(ConfigParser.ConfigParser):
    def get_default(self, section, option, default, func='get'):
        try:
            return getattr(cfg, func)(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default

DEFAULT_CONF_FILE = 'uploader.conf'
cfg = DefaultConfigParser()

cfg.read(DEFAULT_CONF_FILE)
USER=cfg.get_default('google', 'user', None)
PASS=cfg.get_default('google', 'pass', None)

class SampleConfig(object):
  APP_NAME = 'GDataDocumentsListAPISample-v1.0'
  DEBUG = False

def create_client():
  client = gdata.docs.client.DocsClient(source=SampleConfig.APP_NAME)
  try:
    if USER is None:
      gdata.sample_util.authorize_client(
         client,
         1,
         service=client.auth_service,
         source=client.source,
         scopes=client.auth_scopes
      )
    else:
      client.client_login(USER, PASS, source=client.source, service=client.auth_service)
  except gdata.client.BadAuthentication:
    exit('Invalid user credentials given.')
  except gdata.client.Error:
    exit('Login Error')
  return client

def upload_file(local_file, remote_folder, type):
  client = create_client()

  q = gdata.docs.client.DocsQuery(
      title=remote_folder,
      title_exact='true',
      show_collections='true'
  )
  results = client.GetResources(q=q).entry
  if len(results) < 1:
    col = gdata.docs.data.Resource(type='folder', title=remote_folder)
    col = client.CreateResource(col)
  else:
    col = results[0]

  doc = gdata.docs.data.Resource(type=type, title=os.path.basename(local_file))

  media = gdata.data.MediaSource()
  media.SetFileHandle(local_file, type)

  doc = client.CreateResource(doc, media=media, collection=col)

  print 'Uploaded:', doc.title.text, doc.resource_id.text

def main():
  parser = argparse.ArgumentParser(description='Upload file to Google Drive')
  parser.add_argument('file', help='file to upload')
  #parser.add_argument('collection', help='collection for the uploaded document')
  parser.add_argument('type', nargs='?', default='text/plain', help='type of file to upload, default is text/plain')
  args = parser.parse_args()
  local_file = args.file
  remote_folder = "performance_results"
  type = args.type
  upload_file(local_file, remote_folder, type)
  os._exit(0)

# Specifies name of main function.
if __name__ == "__main__":
  sys.exit(main())
