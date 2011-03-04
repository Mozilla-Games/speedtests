CREATE TABLE browser (
    id INT AUTO_INCREMENT,
    PRIMARY KEY (id),
    browsername TEXT COLLATE utf8_bin,
    browserversion TEXT COLLATE utf8_bin,
    platform TEXT COLLATE utf8_bin,
    geckoversion TEXT COLLATE utf8_bin,
    buildid TEXT COLLATE utf8_bin
);
