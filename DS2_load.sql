DROP TABLE IF EXISTS data_2023_feb;
CREATE TABLE IF NOT EXISTS purchased_before_feb AS(
    SELECT * FROM customers
    WHERE event_time < '2023-02-01 00:00:00+01'
        AND event_type = 'purchase'
    ORDER BY event_time ASC);