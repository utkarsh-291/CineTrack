import sqlite3

DB_NAME = "cinetrack.db"


def connect_db():
    connection = sqlite3.connect(DB_NAME)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def create_tables():
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Movies (
        movie_id INTEGER PRIMARY KEY,
        tmdb_id INTEGER NOT NULL UNIQUE,
        title TEXT NOT NULL,
        release_year INTEGER,
        runtime INTEGER,
        status TEXT NOT NULL CHECK(status IN ('Watched', 'Watchlist')),
        date_watched TEXT,
        rating REAL CHECK(rating BETWEEN 0 AND 10),
        overview TEXT,
        poster_path TEXT,
        genres TEXT,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Directors (
        director_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Movie_Directors (
        movie_id INTEGER,
        director_id INTEGER,
        PRIMARY KEY (movie_id, director_id),
        FOREIGN KEY (movie_id) REFERENCES Movies(movie_id) ON DELETE CASCADE,
        FOREIGN KEY (director_id) REFERENCES Directors(director_id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS TV_Series (
        series_id INTEGER PRIMARY KEY,
        tmdb_id INTEGER NOT NULL UNIQUE,
        name TEXT NOT NULL,
        first_air_year INTEGER,
        total_seasons INTEGER,
        total_episodes INTEGER,
        average_episode_runtime INTEGER,
        status TEXT NOT NULL DEFAULT 'Plan to Watch'
            CHECK(status IN ('Plan to Watch', 'Watching', 'Completed', 'On Hold', 'Dropped')),
        rating REAL CHECK(rating BETWEEN 0 AND 10),
        genres TEXT,
        overview TEXT,
        poster_path TEXT,
        notes TEXT
    )
    """)



    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_tables()
    print("Database initialized successfully!")
