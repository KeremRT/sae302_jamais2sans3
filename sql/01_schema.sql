-- On cree la base sae302 si elle manque.
CREATE DATABASE IF NOT EXISTS sae302
    CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
USE sae302;

-- On garde les reglages de chaque scenario et sa version.
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id VARCHAR(8) NOT NULL,
    scenario_version INT NOT NULL,
    config_json LONGTEXT NOT NULL CHECK (JSON_VALID(config_json)),
    config_sha256 CHAR(64) NOT NULL,
    PRIMARY KEY (scenario_id, scenario_version),
    CHECK (scenario_version > 0)
) ENGINE=InnoDB;

-- On associe les deux modes aux memes reglages.
CREATE TABLE IF NOT EXISTS comparisons (
    comparison_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    scenario_id VARCHAR(8) NOT NULL,
    scenario_version INT NOT NULL,
    config_json LONGTEXT NOT NULL CHECK (JSON_VALID(config_json)),
    config_sha256 CHAR(64) NOT NULL,
    data_origin ENUM('SIMULATION', 'EXEMPLE') NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY (scenario_id, scenario_version)
        REFERENCES scenarios (scenario_id, scenario_version)
) ENGINE=InnoDB;

-- On garde un essai par mode avec son etat et sa duree.
CREATE TABLE IF NOT EXISTS trials (
    trial_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    comparison_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    mode ENUM('AVEC', 'SANS') NOT NULL,
    status ENUM('PRET', 'EN_COURS', 'TERMINE', 'INTERROMPU') NOT NULL DEFAULT 'PRET',
    departure_s DECIMAL(18,6) NULL,
    arrival_s DECIMAL(18,6) NULL,
    duration_s DECIMAL(18,6) NULL,
    last_sim_time_s DECIMAL(18,6) NOT NULL DEFAULT 0,
    interruption_reason VARCHAR(32) NULL,
    UNIQUE (comparison_id, mode),
    FOREIGN KEY (comparison_id) REFERENCES comparisons (comparison_id),
    CHECK (last_sim_time_s BETWEEN 0 AND 120),
    CHECK (departure_s IS NULL OR departure_s BETWEEN 0 AND 120),
    CHECK (arrival_s IS NULL OR arrival_s >= departure_s),
    CHECK (duration_s IS NULL OR duration_s >= 0),
    CHECK ((status = 'TERMINE' AND departure_s IS NOT NULL AND arrival_s IS NOT NULL
            AND duration_s = arrival_s - departure_s AND interruption_reason IS NULL)
        OR (status <> 'TERMINE' AND arrival_s IS NULL AND duration_s IS NULL)),
    CHECK ((status = 'INTERROMPU' AND interruption_reason IS NOT NULL)
        OR (status <> 'INTERROMPU' AND interruption_reason IS NULL))
) ENGINE=InnoDB;

-- On garde les messages recus pour chaque essai.
CREATE TABLE IF NOT EXISTS events (
    event_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    trial_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    sim_time_s DECIMAL(18,6) NOT NULL,
    payload_json LONGTEXT NOT NULL CHECK (JSON_VALID(payload_json)),
    received_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY (trial_id) REFERENCES trials (trial_id),
    INDEX events_by_trial (trial_id, sim_time_s),
    CHECK (sim_time_s BETWEEN 0 AND 120)
) ENGINE=InnoDB;
