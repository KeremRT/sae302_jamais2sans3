-- Valeurs FICTIVES pour vérifier les tables : 18 s sans, 15 s avec.
-- Sélectionner une base de test avant d'exécuter ce fichier.
-- Si une commande échoue : ROLLBACK ; ne pas poursuivre au COMMIT.
SET @config = '{"nom":"Exemple fictif"}';
SET @comparaison = UUID();
START TRANSACTION;
INSERT INTO scenarios VALUES ('DEMO', 1, @config, SHA2(@config, 256))
    ON DUPLICATE KEY UPDATE scenario_id = scenario_id;
INSERT INTO comparisons
    (comparison_id, scenario_id, scenario_version, config_json, config_sha256, data_origin)
    VALUES (@comparaison, 'DEMO', 1, @config, SHA2(@config, 256), 'EXEMPLE');
INSERT INTO trials
    (trial_id, comparison_id, mode, status, departure_s, arrival_s, duration_s, last_sim_time_s)
    VALUES (UUID(), @comparaison, 'SANS', 'TERMINE', 0, 18, 18, 18),
           (UUID(), @comparaison, 'AVEC', 'TERMINE', 0, 15, 15, 15);
COMMIT;
SELECT mode, duration_s FROM trials WHERE comparison_id = @comparaison;
