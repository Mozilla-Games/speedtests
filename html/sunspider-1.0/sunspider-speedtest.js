
var SunspiderSpeedtest = {
  startTime: 0,
  iteration: 0,
  numIterations: 2
};

SunspiderSpeedtest.parseIteration = function (url) {
    var idx = url.indexOf('speedtest_iteration=');
    if (idx < 0)
        return false;
    idx += ('speedtest_iteration=').length;
    this.iteration = parseInt(url.substring(idx));
    return true;
};

SunspiderSpeedtest.nextIterationURL = function (url) {
    var stripped = url.replace(/&speedtest_iteration=[0-9]+/, '');
    var iter = this.iteration + 1;
    if (iter > this.numIterations)
        return undefined;
    return stripped + '&speedtest_iteration=' + iter;
};

SunspiderSpeedtest.init = function () {
    console.log("Initializing sunspider speedtest.");
    SpeedTests.init("sunspider");
    var url = window.document.URL;
    this.parseIteration(url);
    console.log("  test " + this.iteration + " of " + this.numIterations);
    this.startTime = (new Date()).getTime();
    start();
};

SunspiderSpeedtest.recordSubScore = function (name, score) {
    console.log("Recording sub result " + name + " => " + score);
    SpeedTests.recordSubResult(name, new Number(score).valueOf());
};

SunspiderSpeedtest.finishIteration = function (callback) {
    if (SpeedTests.results.length > 0) {
        console.log("Finishing iteration " + this.iteration);
        SpeedTests.finish(false, function () {
            SpeedTests.resetResults();
            callback();
        });
    } else {
        // Just finished warmup run.
        callback();
    }
};

SunspiderSpeedtest.recordSunspiderScore = function (score) {
    console.log("Recorded overall sunspider score!");
    SpeedTests.recordSubResult('Sunspider', new Number(score).valueOf());
    var nextURL = this.nextIterationURL(window.document.URL);
    if (!nextURL) {
        SpeedTests.finish();
        return;
    }

    SpeedTests.finish(false, function () {
        window.location = nextURL;
    });
};
