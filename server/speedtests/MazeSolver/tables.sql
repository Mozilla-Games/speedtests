CREATE TABLE MazeSolver (
    id INT AUTO_INCREMENT,
    PRIMARY KEY (id),
    browser_id INT,
    FOREIGN KEY (browser_id) REFERENCES browser(id),
    browser_height INT,
    browser_width INT,
    duration INT,
    teststart TIMESTAMP,
    ip VARCHAR(15) COLLATE utf8_bin
);
