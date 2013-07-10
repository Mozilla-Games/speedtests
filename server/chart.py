#!/usr/bin/env python

import numpy as np
import matplotlib.pyplot as plt

benchmark = 'aquarium'
# browsers = ['firefox', 'firefox-nightly', 'chrome', 'chrome-beta']
scores = {
  'firefox': 21,
  'nigtly': 33,
  'chrome': 27,
  'chrome-beta': 25,
}
browsers = scores.keys();

N = len(browsers);

ind = np.arange(N)  # the x locations for the groups
width = 0.2        # the width of the bars

fig = plt.figure()
ax = fig.add_subplot(111)

offset = 0;
cm = plt.get_cmap('gist_rainbow')
ax.set_color_cycle([cm(1.*i/N) for i in range(N)])

this_color = color = cm(1.*offset/N)
rects = ax.bar(ind+width*offset, scores.values(), width, color=this_color)
offset += 1

# add some
ax.set_ylabel('scores')
ax.set_title(benchmark)
ax.set_xticks(ind+width)
ax.set_xticklabels( browsers )

ax.legend( [rects[0]], [benchmark] )

def autolabel(rects):
    # attach some text labels
    for rect in rects:
        height = rect.get_height()
        ax.text(rect.get_x()+rect.get_width()/2., 1.05*height, '%d'%int(height),
                ha='center', va='bottom')

autolabel(rects)

plt.show()