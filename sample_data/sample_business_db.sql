-- Sample business database seeded into the "sample-business-db" Docker service.
-- Used by the demo scenarios in scripts/demo.py: runtime connection, schema discovery,
-- and text-to-SQL against customers/invoices/products/orders.

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    country VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100) NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    order_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'placed'
);

CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    invoice_value NUMERIC(14, 2) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'unpaid',
    issued_at DATE NOT NULL,
    -- SSN is a deliberately sensitive-looking column to exercise column-permission masking (Phase 4).
    billing_contact_ssn VARCHAR(20)
);

INSERT INTO customers (name, country, email) VALUES
    ('Nile Traders', 'Egypt', 'contact@niletraders.example'),
    ('Delta Foods', 'Egypt', 'sales@deltafoods.example'),
    ('Cairo Textiles', 'Egypt', 'info@cairotextiles.example');

INSERT INTO products (name, category, unit_price) VALUES
    ('Industrial Pump A200', 'Equipment', 15000.00),
    ('Packaging Roll 500m', 'Supplies', 320.00),
    ('Cotton Fabric Bolt', 'Textiles', 800.00);

INSERT INTO orders (customer_id, product_id, quantity, order_date, status) VALUES
    (1, 1, 2, '2026-01-10', 'completed'),
    (2, 2, 50, '2026-01-15', 'completed'),
    (3, 3, 10, '2026-02-01', 'completed'),
    (1, 2, 20, '2026-02-05', 'completed');

INSERT INTO invoices (order_id, invoice_value, status, issued_at, billing_contact_ssn) VALUES
    (1, 30000.00, 'paid', '2026-01-11', '123-45-6789'),
    (2, 16000.00, 'paid', '2026-01-16', '234-56-7890'),
    (3, 8000.00, 'paid', '2026-02-02', '345-67-8901'),
    (4, 6400.00, 'unpaid', '2026-02-06', '123-45-6789');

-- Total paid invoice value: 30000 + 16000 + 8000 = 54000.00 (used by demo Scenario 3).

-- Read-only role for chat query execution, per the assignment's mandatory SQL security controls
-- ("Use read-only source database credentials for normal chat"). The demo/seed data uses this
-- role's credentials when registering the runtime connection, not the schema-owning admin role.
CREATE ROLE sample_readonly WITH LOGIN PASSWORD 'sample_readonly_pw';
GRANT CONNECT ON DATABASE sample_business TO sample_readonly;
GRANT USAGE ON SCHEMA public TO sample_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sample_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sample_readonly;
