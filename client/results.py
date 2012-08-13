# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json

from collections import defaultdict

class SpeedTestReport(object):

    def __init__(self, results):
        self.results = results
        self.best_scores = defaultdict(lambda: {'score': None,
                                                'score_str': '',
                                                'browsers': []})

    def record_best_score(self, test, score, score_str, browser,
                          higher_is_better=True):
        if (self.best_scores[test]['score'] is None) or \
           (higher_is_better and self.best_scores[test]['score'] < score) or \
           (not higher_is_better and self.best_scores[test]['score'] > score):
            self.best_scores[test]['score'] = score
            self.best_scores[test]['score_str'] = score_str
            self.best_scores[test]['browsers'] = [browser]
        elif self.best_scores[test]['score'] == score:
            self.best_scores[test]['browsers'].append(browser)

    def report(self):
        s = 'Results by browser:\n\n'
        for browser, tests in self.results.iteritems():
            s += '%s\n%s\n\n' % (browser, '=' * len(browser))
            for test, results_strs in tests.iteritems():
                s += '  %s\n  %s\n\n' % (test, '-' * len(test))

                if test == 'PsychedelicBrowsing':
                    colorwheel = int(results_strs[0]['colorwheel'])
                    checkerboard = int(results_strs[0]['checkerboard'])
                    s += '  Psychedelic (colorwheel): %d rpm\n' % colorwheel
                    s += '  Hallucinogenic (checkerboard): %d rpm\n\n' % \
                        checkerboard
                    total = colorwheel + checkerboard
                    self.record_best_score(test, total, '%d/%d rpm' %
                                           (colorwheel, checkerboard),
                                           browser)
                    continue

                if test == 'MazeSolver' or test == 'Kraken':
                    score = int(results_strs[0]['duration'])
                    score_str = '%d ms' % score
                    s += '  Duration: %s\n\n' % score_str
                    self.record_best_score(test, score, score_str, browser,
                                           False)
                    continue

                if test == 'test262':
                    score = int(results_strs[0]['score'])
                    score_str = '%d passes' % score
                    s += '  Score: %s\n\n' % score_str
                    self.record_best_score(test, score, score_str, browser)
                    continue

                if test == 'V8':
                    score = int(results_strs[0]['score'])
                    score_str = '%d' % score
                    s += '  Score: %s\n\n' % score_str
                    self.record_best_score(test, score, score_str, browser)
                    continue

                if 'fps' in results_strs[0]:
                    score = 0
                    results = map(lambda x: int(x['fps']), results_strs)
                    if len(results) == 1:
                        score = results[0]
                        score_str = '%d fps' % score
                        s += '  %s\n' % score_str
                    else:
                        if len(results) > 0:
                            s += '  Series:'
                            for r in results:
                                s += ' %3d' % r
                            s += '\n  Mean: %.1d\n' % (sum(results) / len(results))
                            sorted_results = results[:]
                            sorted_results.sort()
                            if len(sorted_results) % 2 == 0:
                                median = (sorted_results[len(sorted_results)/2 - 1] + sorted_results[len(sorted_results)/2]) / 2
                            else:
                                median = sorted_results[len(sorted_results)/2]
                            s += '  Median: %d\n' % median
                            score = median
                            score_str = '%d fps' % score
                        else:
                            s += '  No data.\n'
                    if score:
                        self.record_best_score(test, score, score_str, browser)
                    s += '\n'
                    continue

                if 'value' in results_strs[0]:
                    score = float(results_strs[0]['value'])
                    score_str = '%f' % score
                    s += '  %s\n' % score_str

                    if 'raw' in results_strs[0]:
                        s += '  %s\n' % str(results_strs[0]['raw'])
                        if False:
                            try:
                                raw = results_strs[0]['raw']
                                for line in raw:
                                    s += '      %s: %s\n' % (line['testDescription'], line['testResult'])
                            except Exception, e:
                                print str(e)
                                print "Failed to parse raw results"
                                print results_strs[0]['raw']

                    continue

                s += "!!!! Can't handle result object for test '%s'!\n" % result_strs[0].description
                s += '\n'
        test_list = self.best_scores.keys()
        test_list.sort()
        s += 'Results by test:\n\n'
        for test in test_list:
            s += '%s\n%s\n\n' % (test, '=' * len(test))
            s += ' Best median score: %s (%s)\n\n' % \
                (self.best_scores[test]['score_str'],
                 ', '.join(self.best_scores[test]['browsers']))
        return s


def main():
    results = {
        'firefox': {
            'fishtank': [{'fps': 34}, {'fps': 36}, {'fps': 40}, {'fps': 44}, {'fps': 42}, {'fps': 43}, {'fps': 44}, {'fps': 43}, {'fps': 42}, {'fps': 44}, {'fps': 43}, {'fps': 42}],
            'SantasWorkshop': [{'fps': 10}, {'fps': 7}, {'fps': 4}, {'fps': 3}, {'fps': 3}, {'fps': 3}, {'fps': 3}, {'fps': 3}],
            'PsychedelicBrowsing': [{'colorwheel': 1944, 'checkerboard': 966}]
         },
         'safari': {
            'fishtank': [{'fps': 10}, {'fps': 9}, {'fps': 8}, {'fps': 7}, {'fps': 6}, {'fps': 6}, {'fps': 6}, {'fps': 6}],
            'SantasWorkshop': [{'fps': 3}, {'fps': 3}, {'fps': 3}, {'fps': 3}, {'fps': 3}, {'fps': 3}, {'fps': 3}],
            'PsychedelicBrowsing': [{'colorwheel': 1820, 'checkerboard': 840}]
         }
    }
    report = SpeedTestReport(results)
    print report.report()

if __name__ == '__main__':
    main()

