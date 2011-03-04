CREATE TABLE PsychedelicBrowsing (
    id INT AUTO_INCREMENT,
    PRIMARY KEY (id),
    browser_id INT,
    FOREIGN KEY (browser_id) REFERENCES browser(id),
    browser_height INT,
    browser_width INT,
    colorwheel INT,
    checkerboard INT,
    teststart TIMESTAMP
);
