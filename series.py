import sqlite3

from requests.exceptions import RequestException
from rich.console import Console
from rich.table import Table

from database import connect_db
from tmdb import search_tv, get_tv_details

console = Console()
SERIES_STATUSES = ["Plan to Watch", "Watching", "Completed", "On Hold", "Dropped"]


def _date_year(value):
    return int(value[:4]) if value and len(value) >= 4 and value[:4].isdigit() else None


def _average_runtime(details):
    values = [
        value for value in details.get("episode_run_time", [])
        if isinstance(value, int) and value > 0
    ]
    return round(sum(values) / len(values)) if values else None


def add_series():
    try:
        query = input("\nEnter TV series name: ").strip()
        if not query:
            print("Series name cannot be empty.")
            return

        results = search_tv(query)
        if not results:
            print("No series found.")
            return

        print("\nSearch results:")
        for index, item in enumerate(results[:10], start=1):
            year = (item.get("first_air_date") or "")[:4] or "Unknown"
            print(f"{index}. {item.get('name', 'Untitled')} ({year})")

        choice = int(input("\nSelect series number: "))
        if choice < 1 or choice > min(len(results), 10):
            print("Invalid selection.")
            return

        details = get_tv_details(results[choice - 1]["id"])
        average_runtime = _average_runtime(details)

        print("\nSeries details")
        print("Name:", details.get("name"))
        print("First aired:", details.get("first_air_date") or "Unknown")
        print("Seasons:", details.get("number_of_seasons", 0))
        print("Episodes:", details.get("number_of_episodes", 0))
        print(
            "Average episode duration:",
            f"{average_runtime} minutes" if average_runtime is not None else "Not available"
        )
        print("Genres:", ", ".join(g["name"] for g in details.get("genres", [])) or "Unknown")

        print("\nStatus:")
        for index, status in enumerate(SERIES_STATUSES, start=1):
            print(f"{index}. {status}")
        status_choice = input("Choose status [1]: ").strip() or "1"
        if not status_choice.isdigit() or not 1 <= int(status_choice) <= len(SERIES_STATUSES):
            print("Invalid status.")
            return
        status = SERIES_STATUSES[int(status_choice) - 1]

        rating_input = input("Your rating (0-10, optional): ").strip()
        rating = float(rating_input) if rating_input else None
        if rating is not None and not 0 <= rating <= 10:
            print("Rating must be between 0 and 10.")
            return
        notes = input("Personal notes (optional): ").strip()

        connection = connect_db()
        try:
            connection.execute("""
                INSERT INTO TV_Series (
                    tmdb_id, name, first_air_year, total_seasons, total_episodes,
                    average_episode_runtime, status, rating, genres, overview,
                    poster_path, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                details["id"],
                details.get("name", "Untitled"),
                _date_year(details.get("first_air_date")),
                details.get("number_of_seasons"),
                details.get("number_of_episodes"),
                average_runtime,
                status,
                rating,
                ", ".join(g["name"] for g in details.get("genres", [])),
                details.get("overview"),
                details.get("poster_path"),
                notes or None
            ))
            connection.commit()
            print("\nSeries added to CineTrack.")
        except sqlite3.IntegrityError:
            connection.rollback()
            print("\nThis series is already in your collection.")
        finally:
            connection.close()

    except ValueError:
        print("Invalid input. Check the number or rating you entered.")
    except RequestException as error:
        print("TMDB API error:", error)
    except RuntimeError as error:
        print(error)


def fetch_series(status=None, search_term=None, genre=None, sort_by="name"):
    conditions = []
    parameters = []

    if status:
        conditions.append("status = ?")
        parameters.append(status)
    if search_term:
        conditions.append("name LIKE ?")
        parameters.append(f"%{search_term}%")
    if genre:
        conditions.append("genres LIKE ?")
        parameters.append(f"%{genre}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_by = {
        "name": "name COLLATE NOCASE ASC",
        "rating": "rating DESC, name COLLATE NOCASE ASC",
        "year": "first_air_year DESC, name COLLATE NOCASE ASC"
    }.get(sort_by, "name COLLATE NOCASE ASC")

    query = f"""
        SELECT series_id, name, first_air_year, total_seasons,
               total_episodes, average_episode_runtime, status,
               rating, genres, notes
        FROM TV_Series
        {where_clause}
        ORDER BY {order_by}
    """
    connection = connect_db()
    try:
        return connection.execute(query, parameters).fetchall()
    finally:
        connection.close()


def _display_series(rows, title="TV Series"):
    table = Table(title=f"TV Series: {title}")
    for column in [
        "ID", "Series", "Year", "Seasons", "Episodes",
        "Avg. ep (min)", "Status", "Rating"
    ]:
        table.add_column(column, justify="center" if column != "Series" else "left")

    for row in rows:
        series_id, name, year, seasons, episodes, avg_runtime, status, rating, genres, notes = row
        table.add_row(
            str(series_id),
            name,
            str(year or "N/A"),
            str(seasons if seasons is not None else "N/A"),
            str(episodes if episodes is not None else "N/A"),
            str(avg_runtime if avg_runtime is not None else "N/A"),
            status,
            f"{rating}/10" if rating is not None else "Not rated"
        )

    if rows:
        console.print(table)
    else:
        console.print("[yellow]No TV series found.[/yellow]")


def edit_series(series_id):
    connection = connect_db()
    try:
        row = connection.execute("""
            SELECT name, status, rating, notes
            FROM TV_Series WHERE series_id = ?
        """, (series_id,)).fetchone()
    finally:
        connection.close()

    if not row:
        print("Series not found.")
        return

    name, status, rating, notes = row
    print(f"\nEditing: {name}")
    print("1. Change status")
    print("2. Change rating")
    print("3. Change notes")
    print("4. Delete series")
    print("0. Cancel")
    choice = input("Choose: ").strip()

    try:
        connection = connect_db()
        try:
            if choice == "1":
                for index, value in enumerate(SERIES_STATUSES, start=1):
                    print(f"{index}. {value}")
                selected = int(input("New status: "))
                if not 1 <= selected <= len(SERIES_STATUSES):
                    print("Invalid status.")
                    return
                connection.execute(
                    "UPDATE TV_Series SET status = ? WHERE series_id = ?",
                    (SERIES_STATUSES[selected - 1], series_id)
                )
            elif choice == "2":
                value = input("New rating (0-10, blank to clear): ").strip()
                new_rating = float(value) if value else None
                if new_rating is not None and not 0 <= new_rating <= 10:
                    print("Rating must be between 0 and 10.")
                    return
                connection.execute(
                    "UPDATE TV_Series SET rating = ? WHERE series_id = ?",
                    (new_rating, series_id)
                )
            elif choice == "3":
                value = input("New notes (blank to clear): ").strip()
                connection.execute(
                    "UPDATE TV_Series SET notes = ? WHERE series_id = ?",
                    (value or None, series_id)
                )
            elif choice == "4":
                confirm = input(f"Delete '{name}' permanently? (y/N): ").strip().lower()
                if confirm != "y":
                    print("Deletion cancelled.")
                    return
                connection.execute("DELETE FROM TV_Series WHERE series_id = ?", (series_id,))
                print("Series deleted.")
            elif choice == "0":
                return
            else:
                print("Invalid choice.")
                return

            connection.commit()
            if choice != "4":
                print("Series updated.")
        finally:
            connection.close()
    except ValueError:
        print("Enter a valid number.")
    except sqlite3.Error as error:
        print("Database error:", error)


def browse_series():
    search_term = None
    genre = None
    sort_by = "name"
    status = None

    while True:
        rows = fetch_series(status, search_term, genre, sort_by)
        _display_series(rows, status or "All")

        print("\n1. Search series")
        print("2. Filter by status")
        print("3. Filter by genre")
        print("4. Sort series")
        print("5. Edit or delete series")
        print("6. Clear search and filters")
        print("0. Back")
        choice = input("Choose: ").strip()

        if choice == "1":
            search_term = input("Series name: ").strip() or None
        elif choice == "2":
            print("0. All statuses")
            for index, value in enumerate(SERIES_STATUSES, start=1):
                print(f"{index}. {value}")
            selected = input("Choose status: ").strip()
            if selected == "0":
                status = None
            elif selected.isdigit() and 1 <= int(selected) <= len(SERIES_STATUSES):
                status = SERIES_STATUSES[int(selected) - 1]
            else:
                print("Invalid status.")
        elif choice == "3":
            genre = input("Genre contains: ").strip() or None
        elif choice == "4":
            print("1. Name A-Z\n2. Rating highest first\n3. First aired newest")
            selected = input("Sort by: ").strip()
            sort_by = {"1": "name", "2": "rating", "3": "year"}.get(selected, sort_by)
        elif choice == "5":
            value = input("Enter series ID: ").strip()
            if value.isdigit():
                if any(row[0] == int(value) for row in rows):
                    edit_series(int(value))
                else:
                    print("Choose a series ID visible in the current list.")
            else:
                print("Enter a valid numeric ID.")
        elif choice == "6":
            search_term, genre, status, sort_by = None, None, None, "name"
        elif choice == "0":
            return
        else:
            print("Invalid choice.")


def show_series_statistics():
    connection = connect_db()
    try:
        row = connection.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN status = 'Plan to Watch' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status = 'Watching' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status = 'On Hold' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status = 'Dropped' THEN 1 ELSE 0 END)
            FROM TV_Series
        """).fetchone()
        total, plan, watching, completed, on_hold, dropped = row

        avg_duration = connection.execute("""
            SELECT ROUND(AVG(average_episode_runtime), 1)
            FROM TV_Series
            WHERE average_episode_runtime IS NOT NULL
        """).fetchone()[0]

        avg_rated = connection.execute("""
            SELECT ROUND(AVG(rating), 2)
            FROM TV_Series
            WHERE rating IS NOT NULL
        """).fetchone()[0]
    finally:
        connection.close()

    print("\n========== SERIES STATISTICS ==========")
    print("Total series:", total or 0)
    print("Plan to Watch:", plan or 0)
    print("Watching:", watching or 0)
    print("Completed:", completed or 0)
    print("On Hold:", on_hold or 0)
    print("Dropped:", dropped or 0)
    print(
        "Average episode duration across your series:",
        f"{avg_duration} min" if avg_duration is not None else "N/A"
    )
    print("Average personal series rating:", avg_rated if avg_rated is not None else "N/A")
