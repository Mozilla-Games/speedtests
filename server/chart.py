#!/usr/bin/env python

import numpy as np
import matplotlib.pyplot as plt

#browsers = ['firefox', 'firefox-nightly', 'chrome', 'chrome-beta']
#scores = {
#  'aquarium': [21, 33, 27, 25],
#  'octane': [10, 11, 8, 15],
#  'sunspider-1.0': [32, 22, 14, 23]
#}
benchmarks = ['aquarium', 'octane', 'sunspider-1.0']
scores = {
  'firefox': [21, 10, 32],
  'nightly': [33, 11, 22]
}
browsers = scores.keys()

N = len(benchmarks);

ind = np.arange(N)  # the x locations for the groups
width = 0.2        # the width of the bars

fig = plt.figure()
ax = fig.add_subplot(111)

rects = dict.fromkeys(scores);
offset = 0;
cm = plt.get_cmap('gist_rainbow')
ax.set_color_cycle([cm(1.*i/N) for i in range(N)])
for browser in rects.keys():
  this_color = color = cm(1.*offset/N)
  rects[browser] = ax.bar(ind+width*offset, scores[browser], width, color=this_color)
  offset += 1

# add some
ax.set_ylabel('scores')
ax.set_title('benchmarks')
ax.set_xticks(ind+width)
ax.set_xticklabels( benchmarks )

ax.legend( [rect[0] for rect in rects.values()], browsers )

def autolabel(rects):
    # attach some text labels
    for rect in rects:
        height = rect.get_height()
        ax.text(rect.get_x()+rect.get_width()/2., 1.05*height, '%d'%int(height),
                ha='center', va='bottom')

for rect in rects.values():
  autolabel(rect)

plt.show()