SELECT comparison_id, mode, status, duration_s FROM trials;

SELECT sans.comparison_id,
       sans.duration_s AS temps_sans,
       avec.duration_s AS temps_avec,
       sans.duration_s - avec.duration_s AS gain
FROM trials AS sans
JOIN trials AS avec ON sans.comparison_id = avec.comparison_id
WHERE sans.mode = 'SANS' AND avec.mode = 'AVEC';
