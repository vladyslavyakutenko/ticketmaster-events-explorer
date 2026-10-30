CREATE DATABASE IF NOT EXISTS ticketmaster;
USE ticketmaster;
-- DROP TABLES IF EXISTS europe_data_current, europe_data_archive, pipeline_log;
CREATE TABLE IF NOT EXISTS europe_data_current(
	event_key 
		INT 
        PRIMARY KEY 
        AUTO_INCREMENT,
    event_api_id 
		VARCHAR(50) 
		CHARACTER SET utf8mb4 
        COLLATE utf8mb4_bin 
        UNIQUE 
        NOT NULL,
    event_name VARCHAR(150),
    event_status VARCHAR(20) 
		CHECK (event_status IN (
			'onsale', 'rescheduled', 'offsale', 'cancelled', 'postponed')),
	event_start_local_date DATE,
    event_start_local_time TIME, 
    event_start_datetime_utc DATETIME, 
    event_end_datetime_utc DATETIME,
    onsale_start_datetime_utc DATETIME,
    onsale_end_datetime_utc DATETIME,
    venue_country_code VARCHAR(5),
    venue_country_name VARCHAR(50),
    venue_city VARCHAR(50),
    classification_segment VARCHAR(50),
    classification_genre VARCHAR(50),
    classification_sub_genre VARCHAR(50)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS europe_data_archive(
	event_key 
		INT 
        PRIMARY KEY 
        AUTO_INCREMENT,
    event_api_id 
		VARCHAR(50) 
		CHARACTER SET utf8mb4 
        COLLATE utf8mb4_bin 
        UNIQUE
        NOT NULL,
    event_name VARCHAR(150),
    event_status VARCHAR(20) 
		CHECK (event_status IN (
			'onsale', 'rescheduled', 'offsale', 'cancelled', 'postponed')),
	event_start_local_date DATE,
    event_start_local_time TIME, 
    event_start_datetime_utc DATETIME, 
    event_end_datetime_utc DATETIME,
    onsale_start_datetime_utc DATETIME,
    onsale_end_datetime_utc DATETIME,
    venue_country_code VARCHAR(5),
    venue_country_name VARCHAR(50),
    venue_city VARCHAR(50),
    classification_segment VARCHAR(50),
    classification_genre VARCHAR(50),
    classification_sub_genre VARCHAR(50),
    is_current BOOLEAN NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pipeline_log(
	iteration_id 
		INT
		AUTO_INCREMENT
        PRIMARY KEY,
	iteration_dt DATETIME NOT NULL,
	iteration_status VARCHAR(50)
		CHECK (iteration_status IN (
			'successful', 'error occurred', 'successful: reserve key used')),
	error_text TEXT NULL,
	events_loaded INT NULL,
    new_events_loaded INT NULL,
    events_rewritten INT NULL,
    events_disappeared INT NULL
) ENGINE=InnoDB;

