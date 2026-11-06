-- idempotent demo data for dbstat, every value is a deterministic formula (no random())
DROP SCHEMA IF EXISTS dbstat_demo CASCADE;
CREATE SCHEMA dbstat_demo;
SET search_path = dbstat_demo;

CREATE TABLE users (
    id serial PRIMARY KEY,
    email text,
    age int,
    created_at timestamptz,
    status text
);

CREATE TABLE orders (
    id serial PRIMARY KEY,
    user_id int REFERENCES users(id),
    amount numeric(10,2),
    created_at timestamptz
);

-- 1240 users:
--   email IS NULL for every 31st row (40 rows), the rest repeat after 1180 (some emails occur twice)
--   age IS NULL for 5 rows of every 24 (about 260 rows), age is in 18..92
--   status: deleted for every 10th row, blocked for every 4th of the rest, active otherwise
--   created_at is between 2023-01-03 and 2024-12-27
INSERT INTO users (email, age, created_at, status)
SELECT
    CASE WHEN i % 31 = 0 THEN NULL ELSE 'user' || (i % 1180) || '@example.com' END,
    CASE WHEN i % 24 < 5 THEN NULL ELSE (i * 37) % 75 + 18 END,
    timestamptz '2023-01-03 00:00:00+00' + ((i * 7) % 725) * interval '1 day' + (i % 24) * interval '1 hour',
    CASE WHEN i % 10 = 0 THEN 'deleted' WHEN i % 4 = 0 THEN 'blocked' ELSE 'active' END
FROM generate_series(1, 1240) AS i;

-- 8300 orders
INSERT INTO orders (user_id, amount, created_at)
SELECT
    (i % 1240) + 1,
    ((i * 13) % 490) + 10,
    timestamptz '2023-01-03 00:00:00+00' + ((i * 11) % 725) * interval '1 day' + (i % 24) * interval '1 hour'
FROM generate_series(1, 8300) AS i;
