from datetime import datetime
import sqlite3

from tmdb import search_movies, get_movie_details
from requests.exceptions import RequestException
from database import connect_db
from display import display_movies


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
        if date_watched:
            validate_date(date_watched)

        if status == "Watchlist" and date_watched:
            print("A watchlist movie cannot have a watched date.")
            return

        notes = input("Personal notes (optional): ").strip()
        save_movie(details, status, rating, date_watched, notes)

    except ValueError:
        print("Invalid input. Please enter a valid value.")
    except RequestException as e:
        print("TMDB API error:", e)


def validate_date(date_text):
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format.")


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
        return "inserted"

    except sqlite3.IntegrityError:
        connection.rollback()
        print("\nThis movie already exists in your collection!")
        return "duplicate"
    except sqlite3.Error as e:
        connection.rollback()
        print("\nDatabase error:", e)
        return "error"
    finally:
        connection.close()


def edit_movie(movie_id):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT title, status, rating, date_watched, notes
        FROM Movies
        WHERE movie_id = ?
    """, (movie_id,))
    movie = cursor.fetchone()

    if movie is None:
        connection.close()
        print("Movie not found.")
        return

    title, status, rating, date_watched, notes = movie

    print(f"\nEditing: {title}")
    print("1. Change rating")
    print("2. Change notes")
    print("3. Change date watched")
    print("4. Change status")
    print("5. Delete movie")
    print("0. Cancel")

    choice = input("\nChoose an action: ").strip()

    try:
        if choice == "1":
            value = input("New rating (0-10, leave blank to clear): ").strip()
            new_rating = float(value) if value else None
            if new_rating is not None and not 0 <= new_rating <= 10:
                print("Rating must be between 0 and 10.")
                return
            cursor.execute(
                "UPDATE Movies SET rating = ? WHERE movie_id = ?",
                (new_rating, movie_id)
            )

        elif choice == "2":
            new_notes = input("New notes (leave blank to clear): ").strip()
            cursor.execute(
                "UPDATE Movies SET notes = ? WHERE movie_id = ?",
                (new_notes or None, movie_id)
            )

        elif choice == "3":
            if status != "Watched":
                print("Date watched is only applicable to watched movies. Change the status first.")
                return
            value = input("New date (YYYY-MM-DD, leave blank to clear): ").strip()
            if value:
                validate_date(value)
            cursor.execute(
                "UPDATE Movies SET date_watched = ? WHERE movie_id = ?",
                (value or None, movie_id)
            )

        elif choice == "4":
            new_status = input("New status (Watched/Watchlist): ").strip().title()
            if new_status not in ["Watched", "Watchlist"]:
                print("Invalid status.")
                return

            if new_status == "Watchlist":
                cursor.execute("""
                    UPDATE Movies
                    SET status = ?, date_watched = NULL
                    WHERE movie_id = ?
                """, (new_status, movie_id))
            else:
                value = input("Date watched (YYYY-MM-DD, optional): ").strip()
                if value:
                    validate_date(value)
                cursor.execute("""
                    UPDATE Movies
                    SET status = ?, date_watched = ?
                    WHERE movie_id = ?
                """, (new_status, value or None, movie_id))

        elif choice == "5":
            confirmation = input(
                f"Delete '{title}' permanently? (y/N): "
            ).strip().lower()
            if confirmation != "y":
                print("Deletion cancelled.")
                return

            cursor.execute(
                "DELETE FROM Movies WHERE movie_id = ?",
                (movie_id,)
            )
            connection.commit()
            print("Movie deleted. Its movie-director relationships were deleted too.")
            return

        elif choice == "0":
            print("Edit cancelled.")
            return

        else:
            print("Invalid choice.")
            return

        connection.commit()
        print("Movie details updated successfully.")

    except ValueError as e:
        connection.rollback()
        print("Invalid value:", e)
    except sqlite3.Error as e:
        connection.rollback()
        print("Database error:", e)
    finally:
        connection.close()


def get_movies_by_status(status):

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
            m.notes,
            GROUP_CONCAT(d.name, ', ')
        FROM Movies m
        LEFT JOIN Movie_Directors md
            ON m.movie_id = md.movie_id
        LEFT JOIN Directors d
            ON md.director_id = d.director_id
        WHERE m.status = ?
        GROUP BY m.movie_id
        ORDER BY m.title;
    """, (status,))

    movies = cursor.fetchall()
    connection.close()

    if not movies:
        display_movies([], status)
        return

    formatted_movies = []

    for movie in movies:
        movie_id, title, year, runtime, movie_status, rating, notes, directors = movie
        director_list = directors.split(", ") if directors else []

        formatted_movies.append((
            movie_id,
            title,
            year,
            runtime,
            movie_status,
            rating,
            notes,
            director_list
        ))

    display_movies(formatted_movies, status)

    while True:
        choice = input(
            "\nEnter a movie ID to edit (0 to go back): "
        ).strip()

        if choice == "0":
            return

        if not choice.isdigit():
            print("Please enter a valid numeric movie ID.")
            continue

        edit_movie(int(choice))
        return


def get_watched_movies():
    get_movies_by_status("Watched")


def get_watchlist_movies():
    get_movies_by_status("Watchlist")
