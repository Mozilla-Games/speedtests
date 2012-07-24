// some useful colors (default flot): ["#edc240", "#afd8f8", "#cb4b4b", "#4da74d", "#9440ed"]

var FixedKnownColors = {
  "Chrome": "#edc240",
  "Firefox-tinderbox": "#afd8f8",
  "Firefox-nightly": "#cb4b4b",
  "Firefox": "#4da74d"
};

function FixedColorForBrowser(browserLabel) {
  var space = browserLabel.indexOf(" ");
  var firstPart = space == -1 ? firstPart : browserLabel.substr(0, space);

  return FixedKnownColors[firstPart];
}
