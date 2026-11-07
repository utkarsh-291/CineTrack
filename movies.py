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
    except RuntimeError as e:
        print(e)


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


def fetch_collection(status, search_term=None, filters=None, sort_by="title"):

    conditions = ["m.status = ?"]
    parameters = [status]
    filters = filters or {}

    if search_term:
        conditions.append("""
            (
                m.title LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM Movie_Directors search_md
                    JOIN Directors search_d
                        ON search_d.director_id = search_md.director_id
                    WHERE search_md.movie_id = m.movie_id
                      AND search_d.name LIKE ?
                )
            )
        """)
        search_pattern = f"%{search_term}%"
        parameters.extend([search_pattern, search_pattern])

    if filters.get("genre"):
        conditions.append("m.genres LIKE ?")
        parameters.append(f"%{filters['genre']}%")

    if filters.get("year") is not None:
        conditions.append("m.release_year = ?")
        parameters.append(filters["year"])

    if filters.get("director"):
        conditions.append("""
            EXISTS (
                SELECT 1
                FROM Movie_Directors filter_md
                JOIN Directors filter_d
                    ON filter_d.director_id = filter_md.director_id
                WHERE filter_md.movie_id = m.movie_id
                  AND filter_d.name LIKE ?
            )
        """)
        parameters.append(f"%{filters['director']}%")

    if filters.get("min_rating") is not None:
        conditions.append("m.rating >= ?")
        parameters.append(filters["min_rating"])

    if filters.get("min_runtime") is not None:
        conditions.append("m.runtime >= ?")
        parameters.append(filters["min_runtime"])

    if filters.get("max_runtime") is not None:
        conditions.append("m.runtime <= ?")
        parameters.append(filters["max_runtime"])

    order_by = {
        "title": "m.title COLLATE NOCASE ASC",
        "rating": "m.rating DESC, m.title COLLATE NOCASE ASC",
        "year": "m.release_year DESC, m.title COLLATE NOCASE ASC"
    }.get(sort_by, "m.title COLLATE NOCASE ASC")

    query = f"""
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
        WHERE {" AND ".join(conditions)}
        GROUP BY m.movie_id
        ORDER BY {order_by}
    """

    connection = connect_db()
    cursor = connection.cursor()
    cursor.execute(query, parameters)
    rows = cursor.fetchall()
    connection.close()

    formatted = []
    for row in rows:
        movie_id, title, year, runtime, movie_status, rating, notes, directors = row
        director_list = directors.split(", ") if directors else []
        formatted.append((
            movie_id, title, year, runtime, movie_status,
            rating, notes, director_list
        ))

    return formatted


def choose_filter(filters):

    print("\nFilter by:")
    print("1. Genre")
    print("2. Release year")
    print("3. Director")
    print("4. Minimum rating")
    print("5. Runtime range")
    print("0. Cancel")

    choice = input("Choose a filter: ").strip()

    try:
        if choice == "1":
            value = input("Enter genre (e.g. Action): ").strip()
            if value:
                filters["genre"] = value

        elif choice == "2":
            value = input("Enter release year: ").strip()
            if not value.isdigit() or len(value) != 4:
                print("Enter a valid four-digit year.")
                return
            filters["year"] = int(value)

        elif choice == "3":
            value = input("Enter director name: ").strip()
            if value:
                filters["director"] = value

        elif choice == "4":
            value = float(input("Show movies rated at least (0-10): ").strip())
            if not 0 <= value <= 10:
                print("Rating must be between 0 and 10.")
                return
            filters["min_rating"] = value

        elif choice == "5":
            minimum = input("Minimum runtime in minutes (blank for none): ").strip()
            maximum = input("Maximum runtime in minutes (blank for none): ").strip()

            min_value = int(minimum) if minimum else None
            max_value = int(maximum) if maximum else None

            if min_value is not None and min_value < 0:
                print("Runtime cannot be negative.")
                return
            if max_value is not None and max_value < 0:
                print("Runtime cannot be negative.")
                return
            if min_value is not None and max_value is not None and min_value > max_value:
                print("Minimum runtime cannot exceed maximum runtime.")
                return
            if min_value is None and max_value is None:
                print("No runtime range entered.")
                return

            filters["min_runtime"] = min_value
            filters["max_runtime"] = max_value

        elif choice == "0":
            return

        else:
            print("Invalid choice.")

    except ValueError:
        print("Please enter a valid number.")


def browse_collection(status):

    search_term = None
    filters = {}
    sort_by = "title"

    while True:
        movies = fetch_collection(status, search_term, filters, sort_by)
        display_movies(movies, status)

        print("\nCollection options")
        print("1. Search by title or director")
        print("2. Filter movies")
        print("3. Sort movies")
        print("4. Edit a movie")
        print("5. Clear search and filters")
        print("0. Back")

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            search_term = input("Search title or director: ").strip() or None

        elif choice == "2":
            choose_filter(filters)

        elif choice == "3":
            print("\nSort by:")
            print("1. Alphabetically (A-Z)")
            print("2. Rating (highest first)")
            print("3. Release year (newest first)")
            sort_choice = input("Choose sorting: ").strip()
            sort_options = {"1": "title", "2": "rating", "3": "year"}
            if sort_choice in sort_options:
                sort_by = sort_options[sort_choice]
            else:
                print("Invalid sorting option.")

        elif choice == "4":
            movie_id = input("Enter movie ID to edit: ").strip()
            if movie_id.isdigit():
                edit_movie(int(movie_id))
            else:
                print("Enter a valid numeric movie ID.")

        elif choice == "5":
            search_term = None
            filters = {}
            sort_by = "title"
            print("Search, filters and sorting have been reset.")

        elif choice == "0":
            return

        else:
            print("Invalid choice.")


def get_watched_movies():
    browse_collection("Watched")


def get_watchlist_movies():
    browse_collection("Watchlist")


def show_statistics():

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN status = 'Watched' THEN 1 ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN status = 'Watchlist' THEN 1 ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN status = 'Watched' THEN runtime ELSE 0 END), 0)
        FROM Movies
    """)
    watched_count, watchlist_count, total_runtime = cursor.fetchone()

    print("\n========== CINETRACK STATISTICS ==========")
    print(f"Total movies watched: {watched_count}")
    print(f"Total watchlist movies: {watchlist_count}")
    print(f"Total watch time: {total_runtime / 60:.2f} hours")

    cursor.execute("""
        SELECT title, rating
        FROM Movies
        WHERE status = 'Watched'
          AND rating IS NOT NULL
          AND rating = (
              SELECT MAX(rating)
              FROM Movies
              WHERE status = 'Watched'
                AND rating IS NOT NULL
          )
        ORDER BY title COLLATE NOCASE
    """)
    highest_rated = cursor.fetchall()

    print("\nHighest-rated movie(s):")
    if highest_rated:
        for title, rating in highest_rated:
            print(f"  {title} ({rating}/10)")
    else:
        print("  No watched movies have a rating yet.")

    for label, ordering in [
        ("Longest movie", "runtime DESC"),
        ("Shortest movie", "runtime ASC")
    ]:
        cursor.execute(f"""
            SELECT title, runtime
            FROM Movies
            WHERE status = 'Watched' AND runtime IS NOT NULL
            ORDER BY {ordering}, title COLLATE NOCASE
            LIMIT 1
        """)
        result = cursor.fetchone()

        if result:
            title, runtime = result
            print(f"{label}: {title} ({runtime} minutes)")
        else:
            print(f"{label}: No runtime data available.")

    connection.close()
