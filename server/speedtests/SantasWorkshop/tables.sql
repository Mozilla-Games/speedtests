CREATE TABLE SantasWorkshop (
    id INT AUTO_INCREMENT,
    PRIMARY KEY (id),
    browser_id INT,
    FOREIGN KEY (browser_id) REFERENCES browser(id),
    num_presents INT,
    num_elves INT,
    ppm INT,
    fps INT,
    browser_height INT,
    browser_width INT,
    etms INT,
    teststart TIMESTAMP,
    ip VARCHAR(15) COLLATE utf8_bin
);
