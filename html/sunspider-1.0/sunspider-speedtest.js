
var SunspiderSpeedtest = {
  startTime: 0,
  iteration: 0,
  numIterations: 2,
  subScores: {}
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
    this.subScores[name] = score;
};

SunspiderSpeedtest.recordSubScore = function (name, score) {
    console.log("Recording sub result " + name + " => " + score);
    this.subScores[name] = score;
    SpeedTests.recordSubResult(name, new Number(score).valueOf());
};

SunspiderSpeedtest.recordSectionAndTotalScores = function () {
    var self = this;
    var scoreNames = Object.getOwnPropertyNames(self.subScores);
    var total = 0;
    var sectionTotals = {};
    scoreNames.forEach(function (name) {
        var score = self.subScores[name];
        total += score;
        var section = name.substr(0, name.indexOf('-'));
        if (sectionTotals[section] === undefined)
            sectionTotals[section] = 0;
        sectionTotals[section] += score;
    });
    var sectionNames = Object.getOwnPropertyNames(sectionTotals);
    sectionNames.forEach(function (section) {
        var secTotal = sectionTotals[section];
        self.recordSubScore("section-" + section, secTotal);
    });
    self.recordSubScore("total", total);
};

SunspiderSpeedtest.finishIteration = function (callback) {
    var self = this;
    if (SpeedTests.results.length > 0) {
        console.log("Finishing iteration " + this.iteration);
        // Calculate and add section and total scores.
        self.recordSectionAndTotalScores();

        SpeedTests.finish(false, function () {
            self.subScores = {};
            SpeedTests.resetResults();
            callback();
        });
    } else {
        // Just finished warmup run.
        callback();
    }
};

SunspiderSpeedtest.finish = function () {
    this.recordSectionAndTotalScores();
    SpeedTests.finish(true);
};
