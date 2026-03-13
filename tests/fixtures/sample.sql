/*
Sample SQL file for testing.
*/

CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIEW active_users AS
SELECT id, name, email
FROM users
WHERE status = 'active';

WITH monthly_stats AS (
    SELECT
        DATE_TRUNC('month', created_at) AS month,
        COUNT(*) AS user_count
    FROM users
    GROUP BY 1
)
SELECT * FROM monthly_stats;
