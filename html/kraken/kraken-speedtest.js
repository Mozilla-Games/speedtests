
var KrakenSpeedtest = {
  startTime: 0,
  iteration: 0,
  numIterations: 1
};

KrakenSpeedtest.parseIteration = function (url) {
    var idx = url.indexOf('speedtest_iteration=');
    if (idx < 0)
        return false;
    idx += ('speedtest_iteration=').length;
    this.iteration = parseInt(url.substring(idx));
    return true;
};

KrakenSpeedtest.nextIterationURL = function (url) {
    var stripped = url.replace(/&speedtest_iteration=[0-9]+/, '');
    var iter = this.iteration + 1;
    if (iter > this.numIterations)
        return undefined;
    return stripped + '&speedtest_iteration=' + iter;
};

KrakenSpeedtest.init = function () {
    SpeedTests.init("octane");
    var url = window.document.URL;
    if (!this.parseIteration(url)) {
        window.location = this.nextIterationURL(url);
        return;
    }

    this.startTime = (new Date()).getTime();
    return true;
};

KrakenSpeedtest.recordSubScore = function (name, score) {
    SpeedTests.recordSubResult(name, new Number(score).valueOf());
};

KrakenSpeedtest.recordKrakenScore = function (score) {
    console.log("Recorded overall kraken score!");
    SpeedTests.recordSubResult('Kraken', new Number(score).valueOf());
    var nextURL = this.nextIterationURL(window.document.URL);
    if (!nextURL) {
        SpeedTests.finish();
        return;
    }

    SpeedTests.finish(false, function () {
        window.location = nextURL;
    });
};
