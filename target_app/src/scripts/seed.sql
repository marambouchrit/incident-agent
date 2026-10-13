-- Demo data. Usage: psql -v orders=1500000 -f seed.sql
INSERT INTO users (email, name, created_at)
SELECT 'user' || g || '@example.com', 'User ' || g, now() - random() * interval '400 days'
FROM generate_series(1, 2000) AS g;

INSERT INTO products (name, category, price_cents, created_at)
SELECT
    (ARRAY['Classic','Mini','Pro','Eco','Smart','Deluxe','Travel','Light'])[1 + (g % 8)] || ' ' ||
    (ARRAY['Lamp','Backpack','Notebook','Speaker','Kettle','Puzzle','Kit','Set','Bottle','Blanket'])[1 + (g % 10)] || ' ' || g,
    (ARRAY['books','electronics','home','toys','garden','sports','beauty','grocery'])[1 + (g % 8)],
    500 + (random() * 20000)::int,
    now() - random() * interval '400 days'
FROM generate_series(1, 500) AS g;

INSERT INTO inventory (product_id, quantity)
SELECT id, 100000 FROM products;

INSERT INTO orders (user_id, status, total_cents, created_at)
SELECT 1 + floor(random() * 2000)::int, 'paid', 500 + floor(random() * 20000)::int, now() - random() * interval '90 days'
FROM generate_series(1, :orders);

INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
SELECT id, 1 + floor(random() * 500)::int, 1 + floor(random() * 3)::int, total_cents
FROM orders;

ANALYZE;
