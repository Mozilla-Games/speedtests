
var CanvasMarkSpeedtest = {
  startTime: 0,
  iteration: 0,
  numIterations: 1,
  subScores: [{}]
};

CanvasMarkSpeedtest.latestScoreObject = function () {
    if (this.subScores.length == 0)
        return undefined;
    return this.subScores[this.subScores.length - 1];
};

CanvasMarkSpeedtest.parseIteration = function (url) {
    var idx = url.indexOf('speedtest_iteration=');
    if (idx < 0)
        return false;
    idx += ('speedtest_iteration=').length;
    this.iteration = parseInt(url.substring(idx));
    return true;
};

CanvasMarkSpeedtest.nextIterationURL = function (url) {
    var stripped = url.replace(/&speedtest_iteration=[0-9]+/, '');
    var iter = this.iteration + 1;
    if (iter > this.numIterations)
        return undefined;
    return stripped + '&speedtest_iteration=' + iter;
};

CanvasMarkSpeedtest.init = function () {
    console.log("Initializing CanvasMark speedtest.");
    SpeedTests.init("CanvasMark");
    var url = window.document.URL;
    if(!this.parseIteration(url)) {
        window.location = this.nextIterationURL(url);
    }
    this.parseIteration(url);
    console.log("  test " + this.iteration + " of " + this.numIterations);
    this.startTime = (new Date()).getTime();
};

CanvasMarkSpeedtest.recordSubScore = function (name, score) {
    console.log("Recording sub result " + name + " => " + score);
    this.latestScoreObject()[name] = score;
};

CanvasMarkSpeedtest.recordSectionAndTotalScores = function () {
    var self = this;
    var scores = self.latestScoreObject();
    if (!scores)
        return;
    var scoreNames = Object.getOwnPropertyNames(scores);
    var total = 0;
    var sectionTotals = {};
    scoreNames.forEach(function (name) {
        var score = scores[name];
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

CanvasMarkSpeedtest.finishIteration = function () {
    // Calculate and add section and total scores.
    if (this.subScores.length > 0)
        this.recordSectionAndTotalScores();
    this.subScores.push({});
};

CanvasMarkSpeedtest.calculateFinalScores = function () {
    // Collect list of scores by test
    var listScores = {};
    this.subScores.forEach(function (scores) {
        Object.getOwnPropertyNames(scores).forEach(function (name) {
            if (!listScores[name])
                listScores[name] = [];
            listScores[name].push(scores[name]);
        });
    });

    // Calculate mean and standard deviation, and record.
    Object.getOwnPropertyNames(listScores).forEach(function (name) {
        var count = listScores[name].length;
        var sum = 0;
        listScores[name].forEach(function (score) {
            sum += score;
        });
        var mean = sum / count;

        var sumdiffsq = 0;
        listScores[name].forEach(function (score) {
            sumdiffsq += Math.pow(Math.abs(mean - score), 2);
        });
        var variance = sumdiffsq / (count - 1);
        var dev = Math.sqrt(variance);

        SpeedTests.recordSubResult(name, mean, {deviation:dev});
    });
};

CanvasMarkSpeedtest.finish = function () {
    this.recordSectionAndTotalScores();
    this.calculateFinalScores();
    console.log("Finishing iteration " + this.iteration);
    var url = this.nextIterationURL(window.document.URL);
    if (!url) {
        SpeedTests.finish(true);
        return;
    }

    SpeedTests.finish(false, function () {
        window.location = url;
    });
};
