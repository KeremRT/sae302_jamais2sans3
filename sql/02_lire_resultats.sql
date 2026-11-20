USE sae302;
-- On affiche les deux durees cote a cote. Le gain est calcule si les deux essais sont termines.
SELECT c.comparison_id, c.scenario_id, c.scenario_version, c.data_origin,
       s.status AS etat_sans, a.status AS etat_avec,
       s.duration_s AS temps_sans_s, a.duration_s AS temps_avec_s,
       CASE WHEN s.status = 'TERMINE' AND a.status = 'TERMINE'
            THEN s.duration_s - a.duration_s END AS gain_s
-- On garde aussi les comparaisons auxquelles il manque un essai.
FROM comparisons AS c
LEFT JOIN trials AS s ON s.comparison_id = c.comparison_id AND s.mode = 'SANS'
LEFT JOIN trials AS a ON a.comparison_id = c.comparison_id AND a.mode = 'AVEC'
ORDER BY c.created_at, c.comparison_id;
