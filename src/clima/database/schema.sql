CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    email TEXT UNIQUE COLLATE NOCASE,
    phone TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    preferences TEXT NOT NULL,
    settings TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    photo TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL,
    color TEXT NOT NULL,
    seasons TEXT NOT NULL,
    min_temperature INTEGER NOT NULL,
    max_temperature INTEGER NOT NULL,
    part TEXT NOT NULL,
    dress_code TEXT NOT NULL,
    style TEXT NOT NULL,
    silhouette TEXT NOT NULL,
    material TEXT NOT NULL,
    in_laundry INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS items_user_id_idx ON items(user_id);
CREATE TABLE IF NOT EXISTS outfits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    outfit_date TEXT NOT NULL,
    place TEXT NOT NULL,
    occasion TEXT NOT NULL,
    selected INTEGER NOT NULL DEFAULT 0,
    rating INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS outfits_user_date_idx ON outfits(user_id, outfit_date);
CREATE TABLE IF NOT EXISTS outfit_items (
    outfit_id INTEGER NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    PRIMARY KEY (outfit_id, item_id)
);
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    outfit_id INTEGER NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, outfit_id)
);
