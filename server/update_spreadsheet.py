#!/usr/bin/python

import datetime
import getopt
import gdata.spreadsheet.service
import json
import math
import sys

SPREADSHEET_TITLE = 'Auto-updated Results'
WORKSHEET_NAME = {'octane':'Octane', 'sunspider-1.0':'SunSpider'}
EMAIL = 'GOOGLE_EMAIL_ADDRESS'
PASSWORD = 'GOOGLE_PASSWORD'

def login():
    client = gdata.spreadsheet.service.SpreadsheetsService()
    client.email = EMAIL
    client.password = PASSWORD
    client.source = 'SpeedTests'
    client.ProgrammaticLogin()
    return client

def find_spreadsheet(client):
    ssfeed = client.GetSpreadsheetsFeed()
    for ent in ssfeed.entry:
        if ent.title.text == SPREADSHEET_TITLE:
            return ent
    return None

def get_spreadsheet_id(spreadsheet):
    return spreadsheet.id.text.split('/')[-1]

def find_worksheet(client, spreadsheet, name):
    wsfeed = client.GetWorksheetsFeed(get_spreadsheet_id(spreadsheet))
    for ent in wsfeed.entry:
        if ent.title.text == WORKSHEET_NAME[name]:
            return ent
    return None

def get_worksheet_id(worksheet):
    return worksheet.id.text.split('/')[-1]

class Browser:
    def __init__(self, id, info):
        self.id = id
        self.version = info['version']
        self.platform = info['platform']
        self.name = info['name']
        self.benchScoreMap = {}

    def fullname(self):
        return '%s %s' % (self.name, self.version)

    def addBenchScores(self, name, uuid):
        bs = BenchScores(self, name, uuid)
        self.benchScoreMap[name] = bs
        return bs

    def benchScores(self, name):
        return self.benchScoreMap[name]

    def benches(self):
        return self.benchScoreMap.keys()

class BenchScores:
    def __init__(self, browser, name, uuid):
        self.browser = browser
        self.name = name
        self.uuid = uuid
        self.progScoreMap = {}

    def addProgScores(self, name):
        ps = ProgScores(self, name)
        self.progScoreMap[name] = ps
        return ps

    def progScores(self, name):
        return self.progScoreMap[name]

    def progs(self):
        return self.progScoreMap.keys()

class ProgScores:
    def __init__(self, benchScores, name):
        self.benchScores = benchScores
        self.name = name
        self.scores = []

    def addScore(self, score):
        self.scores.append(score)

    def mean(self):
        return sum(self.scores) / float(len(self.scores))

    def stddev(self):
        num = len(self.scores)
        mean = sum(self.scores) / float(num)
        diffsq = [(mean-x)**2 for x in self.scores]
        var = sum(diffsq) / float(num - 1)
        return math.sqrt(var)

    def stderr(self):
        return self.stddev() / math.sqrt(len(self.scores))

def load_json(data):
    browsers = {}
    for (id, info) in data['browsers'].items():
        browsers[int(id)] = Browser(int(id), info)

    for (id, scores) in data['scores'].items():
        b = browsers[int(id)]
        for (bench, bench_info) in scores.items():
            bs = b.addBenchScores(bench, bench_info['uuid'])

            for (prog, prog_scores) in bench_info['scores'].items():
                ps = bs.addProgScores(prog)

                for (score_id, score_info) in prog_scores.items():
                    ps.addScore(score_info['score'])

    return browsers.values()

def add_scores(client, spreadsheet, time, platform, browser, benchmark, results):
    worksheet = find_worksheet(client, spreadsheet, str(benchmark))
    if not worksheet:
        raise Exception("Failed to find worksheet")

    s_id = get_spreadsheet_id(spreadsheet)
    w_id = get_worksheet_id(worksheet)
    r = {}
    for (key, score) in results.items():
        s = str(key).lower()
        if s[0].isdigit():
            s = 'x' + s
        r[s] = score
    r['time'] = time
    r['platform'] = platform
    r['browser'] = browser
    client.InsertRow(r, s_id, w_id)

PLATFORM='Galaxy S'
def main():
    client = login()
    sheet = find_spreadsheet(client)
    browser_data = load_json(json.loads(sys.stdin.read()))
    time = str(datetime.datetime.now())

    for browser in browser_data:
        for bench in browser.benches():
            bs = browser.benchScores(bench)
            results = {}
            for prog in bs.progs():
                ps = bs.progScores(prog)
                results[str(prog)] = str(ps.mean())
            add_scores(client, sheet, time, PLATFORM, browser.fullname(), bench, results)

    dashed_benches = set()
    for browser in browser_data:
        for bench in browser.benches():
            if bench not in dashed_benches:
                add_scores(client, sheet, ' ', ' ', ' ', bench, {})
                dashed_benches.add(bench)

main()

#documents_feed = client.GetDocumentListFeed()
#for document_entry in documents_feed.entry:
#    print document_entry.title.text
