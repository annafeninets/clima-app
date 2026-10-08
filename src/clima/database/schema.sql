-- Схема PostgreSQL. Выполняется при старте backend, все операторы идемпотентны.

CREATE TABLE IF NOT EXISTS users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    email TEXT,
    phone TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    preferences JSONB NOT NULL,
    settings JSONB NOT NULL
);
-- email регистронезависимый и уникальный; NULL (вход по телефону) не конфликтуют.
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_idx ON users (lower(email));

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);

CREATE TABLE IF NOT EXISTS items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL,
    photo TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL,
    color TEXT NOT NULL,
    seasons JSONB NOT NULL,
    min_temperature INTEGER NOT NULL,
    max_temperature INTEGER NOT NULL,
    part TEXT NOT NULL,
    dress_code TEXT NOT NULL,
    style TEXT NOT NULL,
    silhouette TEXT NOT NULL,
    material TEXT NOT NULL,
    in_laundry BOOLEAN NOT NULL DEFAULT FALSE,
    deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS items_user_id_idx ON items(user_id);

CREATE TABLE IF NOT EXISTS outfits (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL,
    outfit_date DATE NOT NULL,
    place TEXT NOT NULL,
    occasion TEXT NOT NULL,
    selected BOOLEAN NOT NULL DEFAULT FALSE,
    rating INTEGER NOT NULL DEFAULT 0 CHECK (rating BETWEEN 0 AND 5)
);
CREATE INDEX IF NOT EXISTS outfits_user_date_idx ON outfits(user_id, outfit_date);

CREATE TABLE IF NOT EXISTS outfit_items (
    outfit_id BIGINT NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
    item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    PRIMARY KEY (outfit_id, item_id)
);
CREATE INDEX IF NOT EXISTS outfit_items_item_idx ON outfit_items(item_id);

CREATE TABLE IF NOT EXISTS favorites (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    outfit_id BIGINT NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (user_id, outfit_id)
);
CREATE INDEX IF NOT EXISTS favorites_outfit_idx ON favorites(outfit_id);
