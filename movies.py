from tmdb import search_movies, get_movie_details
from requests.exceptions import RequestException
from database import connect_db
from display import display_movies
import sqlite3

def add_movie():

    try:
        query = input("\nEnter movie name: ").strip()

        if not query:
            print("Movie name cannot be empty.")
            return

        results = search_movies(query)

        if not results:
            print("No movies found.")
            return

        print("\nSearch Results:\n")

        for index, movie in enumerate(results[:10], start=1):
            title = movie["title"]
            release_date = movie.get("release_date") or "Unknown"

            print(f"{index}. {title} ({release_date})")

        choice = int(input("\nSelect movie number: "))

        if choice < 1 or choice > min(len(results), 10):
            print("Invalid selection.")
            return

        selected_movie = results[choice - 1]

        details = get_movie_details(selected_movie["id"])

        print("\nMovie Details")
        print("Title:", details["title"])
        print("Year:", details.get("release_date"))
        print("Runtime:", details.get("runtime"), "minutes")
        print("Genres:", [g["name"] for g in details.get("genres", [])])

        directors = [
            person["name"]
            for person in details.get("credits", {}).get("crew", [])
            if person["job"] == "Director"
        ]

        print("Directors:", directors)

        status = input("\nStatus (Watched/Watchlist): ").strip().title()

        if status not in ["Watched", "Watchlist"]:
            print("Invalid status.")
            return

        rating_input = input("Your rating (0-10, optional): ").strip()
        rating = float(rating_input) if rating_input else None

        if rating is not None and not 0 <= rating <= 10:
            print("Rating must be between 0 and 10.")
            return

        date_watched = input("Date watched (optional, YYYY-MM-DD): ").strip()

        notes = input("Personal notes (optional): ").strip()

        save_movie(details, status, rating, date_watched, notes)

    except ValueError:
        print("Invalid input. Please enter a valid number.")

    except RequestException as e:
        print("TMDB API error:", e)

def save_movie(details, status, rating, date_watched, notes):

    connection = connect_db()
    cursor = connection.cursor()

    try:
        release_date = details.get("release_date") or None

        release_year = (
            int(release_date[:4])
            if release_date and len(release_date) >= 4
            else None
        )

        genres = ", ".join(
            genre["name"] for genre in details.get("genres", [])
        )

        cursor.execute("""
    INSERT INTO Movies (
        tmdb_id, title, release_year, runtime,
        status, date_watched, rating,
        overview, poster_path, genres, notes
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    details["id"],
    details["title"],
    release_year,
    details.get("runtime"),
    status,
    date_watched or None,
    rating,
    details.get("overview"),
    details.get("poster_path"),
    genres,
    notes
))

        movie_id = cursor.lastrowid

        directors = [
            person["name"]
            for person in details.get("credits", {}).get("crew", [])
            if person["job"] == "Director"
        ]

        for director in directors:

            cursor.execute("""
                INSERT OR IGNORE INTO Directors (name)
                VALUES (?)
            """, (director,))

            cursor.execute("""
                SELECT director_id FROM Directors
                WHERE name = ?
            """, (director,))

            director_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO Movie_Directors (movie_id, director_id)
                VALUES (?, ?)
            """, (movie_id, director_id))

        connection.commit()

        print("\nMovie successfully added to CineTrack!")

    except sqlite3.IntegrityError:
        connection.rollback()
        print("\nThis movie already exists in your collection!")

    except sqlite3.Error as e:
        connection.rollback()
        print("\nDatabase error:", e)

    finally:
        connection.close()

def get_all_movies():

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            m.movie_id,
            m.title,
            m.release_year,
            m.runtime,
            m.status,
            m.rating,
            GROUP_CONCAT(d.name, ', ')
        FROM Movies m
        LEFT JOIN Movie_Directors md
            ON m.movie_id = md.movie_id
        LEFT JOIN Directors d
            ON md.director_id = d.director_id
        GROUP BY m.movie_id
        ORDER BY m.title;
    """)

    movies = cursor.fetchall()
    connection.close()

    formatted_movies = []

    for movie in movies:

        movie_id, title, year, runtime, status, rating, directors = movie

        director_list = directors.split(", ") if directors else []

        formatted_movies.append((
            movie_id,
            title,
            year,
            runtime,
            status,
            rating,
            director_list
        ))

    display_movies(formatted_movies)