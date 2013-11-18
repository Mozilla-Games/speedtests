
var OctaneSpeedtest = {
  startTime: 0,
  iteration: 0,
  numIterations: 1
};

OctaneSpeedtest.parseIteration = function (url) {
    var idx = url.indexOf('speedtest_iteration=');
    if (idx < 0)
        return false;
    idx += ('speedtest_iteration=').length;
    this.iteration = parseInt(url.substring(idx));
    return true;
};

OctaneSpeedtest.nextIterationURL = function (url) {
    var stripped = url.replace(/&speedtest_iteration=[0-9]+/, '');
    var iter = this.iteration + 1;
    if (iter > this.numIterations)
        return undefined;
    return stripped + '&speedtest_iteration=' + iter;
};

OctaneSpeedtest.init = function () {
    SpeedTests.init("octane");
    var url = window.document.URL;
    if (!this.parseIteration(url)) {
        window.location = this.nextIterationURL(url);
        return;
    }

    this.startTime = (new Date()).getTime();
    return true;
};

OctaneSpeedtest.recordSubScore = function (name, score) {
    SpeedTests.recordSubResult(name, new Number(score).valueOf());
};

OctaneSpeedtest.recordOctaneScore = function (score) {
    console.log("Recorded overall octane score!");
    SpeedTests.recordSubResult('Octane', new Number(score).valueOf());
    var nextURL = this.nextIterationURL(window.document.URL);
    if (!nextURL) {
        SpeedTests.finish();
        return;
    }

    SpeedTests.finish(false, function () {
        window.location = nextURL;
    });
};
