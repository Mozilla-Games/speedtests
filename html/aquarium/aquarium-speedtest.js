
var AquariumSpeedtest = {
  startTime: 0,
  loaded: false,
  recording: false,
  submitted: false,
  values: [],
  skipTime: 15000, // wait 15s before recording fps
  testDuration: 30000, // record for 30s
};

AquariumSpeedtest.init = function() {
  SpeedTests.init("webgl-aquarium");
  this.startTime = (new Date()).getTime();
};

AquariumSpeedtest.fpsUpdate = function(avg) {
  this.values.push(avg);
  var now = (new Date()).getTime();
  var elapsed = now - this.startTime;

  if (!this.loaded || this.submitted)
    return;

  if (elapsed < this.skipTime)
    return;

  this.values.push(avg);

  if (elapsed > (this.skipTime + this.testDuration)) {
    var numFrames = this.values.length;
    var total = 0;
    for (var i = 0; i < numFrames; ++i)
      total += this.values[i];

    var average = total / numFrames;
    var sorted = this.values;
    sorted.sort(function(a,b) { if (a<b) return -1; if (a>b) return 1; return 0; });
    var median = sorted[Math.floor(numFrames / 2)];

    var extra = {
      testDescription: "WebGL Aquarium",
      testResult: average,
      min: sorted[0],
      max: sorted[numFrames-1],
      median: median,
    };

    this.submitted = true;

    var testName = "webgl-aquarium";
    SpeedTests.recordResult(average, extra);
    SpeedTests.finish();
  }
};


$(window).load(function() {
  AquariumSpeedtest.loaded = true;
});
