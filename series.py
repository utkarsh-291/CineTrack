from datetime import datetime
import sqlite3

from requests.exceptions import RequestException
from rich.console import Console
from rich.table import Table

from database import connect_db
from tmdb import search_tv, get_tv_details, get_tv_season_details

console = Console()
SERIES_STATUSES = ["Plan to Watch", "Watching", "Completed", "On Hold", "Dropped"]


def _date_year(value):
    return int(value[:4]) if value and len(value) >= 4 and value[:4].isdigit() else None


def _validate_date(value):
    if value:
        datetime.strptime(value, "%Y-%m-%d")


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
        print("\nSeries details")
        print("Name:", details.get("name"))
        print("First aired:", details.get("first_air_date") or "Unknown")
        print("Seasons:", details.get("number_of_seasons", 0))
        print("Episodes:", details.get("number_of_episodes", 0))
        print("Average episode duration:", _average_runtime(details), "minutes")
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
                _average_runtime(details),
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


def _average_runtime(details):
    values = [value for value in details.get("episode_run_time", []) if isinstance(value, int) and value > 0]
    return round(sum(values) / len(values)) if values else None


def fetch_series(status=None, search_term=None, genre=None, sort_by="name"):
    conditions = []
    parameters = []

    if status:
        conditions.append("s.status = ?")
        parameters.append(status)
    if search_term:
        conditions.append("s.name LIKE ?")
        parameters.append(f"%{search_term}%")
    if genre:
        conditions.append("s.genres LIKE ?")
        parameters.append(f"%{genre}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_by = {
        "name": "s.name COLLATE NOCASE ASC",
        "rating": "s.rating DESC, s.name COLLATE NOCASE ASC",
        "year": "s.first_air_year DESC, s.name COLLATE NOCASE ASC",
        "progress": "watched_count DESC, s.name COLLATE NOCASE ASC"
    }.get(sort_by, "s.name COLLATE NOCASE ASC")

    query = f"""
        SELECT s.series_id, s.name, s.first_air_year, s.total_seasons,
               s.total_episodes, s.average_episode_runtime, s.status,
               s.rating, COUNT(p.progress_id) AS watched_count,
               s.genres, s.notes
        FROM TV_Series s
        LEFT JOIN Series_Progress p ON p.series_id = s.series_id
        {where_clause}
        GROUP BY s.series_id
        ORDER BY {order_by}
    """
    connection = connect_db()
    try:
        return connection.execute(query, parameters).fetchall()
    finally:
        connection.close()


def _display_series(rows, title="TV Series"):
    table = Table(title=f"TV Series: {title}")
    for column in ["ID", "Series", "Year", "Seasons", "Episodes", "Avg. ep (min)", "Progress", "Status", "Rating"]:
        table.add_column(column, justify="center" if column != "Series" else "left")
    for row in rows:
        series_id, name, year, seasons, episodes, avg_runtime, status, rating, watched, genres, notes = row
        episode_total = str(episodes) if episodes is not None else "?"
        table.add_row(
            str(series_id), name, str(year or "N/A"),
            str(seasons if seasons is not None else "N/A"),
            episode_total,
            str(avg_runtime if avg_runtime is not None else "N/A"),
            f"{watched}/{episode_total}",
            status,
            f"{rating}/10" if rating is not None else "Not rated"
        )
    if rows:
        console.print(table)
    else:
        console.print("[yellow]No TV series found.[/yellow]")


def _show_progress(series_id, name):
    connection = connect_db()
    try:
        rows = connection.execute("""
            SELECT season_number, episode_number, episode_name, watched_on
            FROM Series_Progress
            WHERE series_id = ?
            ORDER BY season_number, episode_number
        """, (series_id,)).fetchall()
    finally:
        connection.close()

    print(f"\nEpisode progress: {name}")
    if not rows:
        print("No episodes marked as watched yet.")
        return
    table = Table(title="Watched episodes")
    table.add_column("Season")
    table.add_column("Episode")
    table.add_column("Episode name")
    table.add_column("Watched on")
    for season, episode, episode_name, watched_on in rows:
        table.add_row(str(season), str(episode), episode_name or "Unknown", watched_on or "Not recorded")
    console.print(table)


def update_episode_progress(series_id, name):
    connection = connect_db()
    try:
        series = connection.execute(
            "SELECT tmdb_id FROM TV_Series WHERE series_id = ?", (series_id,)
        ).fetchone()
    finally:
        connection.close()
    if not series:
        print("Series not found.")
        return

    try:
        details = get_tv_details(series[0])
        seasons = [s for s in details.get("seasons", []) if s.get("episode_count", 0) > 0]
        if not seasons:
            print("TMDB has no season information for this series.")
            return

        print(f"\nSeasons for {name}:")
        for index, season in enumerate(seasons, start=1):
            print(f"{index}. Season {season['season_number']}: {season.get('name', 'Season')} ({season.get('episode_count', 0)} episodes)")
        season_choice = int(input("Select season: "))
        if season_choice < 1 or season_choice > len(seasons):
            print("Invalid season selection.")
            return

        season_number = seasons[season_choice - 1]["season_number"]
        season_data = get_tv_season_details(series[0], season_number)
        episodes = season_data.get("episodes", [])
        if not episodes:
            print("No episodes returned for this season.")
            return

        print("\nEpisodes:")
        for episode in episodes:
            number = episode.get("episode_number")
            title = episode.get("name") or "Untitled"
            print(f"{number}. {title}")

        action = input("\n1. Mark episode watched\n2. Remove watched mark\n0. Cancel\nChoose: ").strip()
        if action == "0":
            return
        episode_number = int(input("Episode number: "))
        selected = next((ep for ep in episodes if ep.get("episode_number") == episode_number), None)
        if not selected:
            print("That episode number is not in the selected season.")
            return

        if action == "1":
            watched_on = input("Date watched (YYYY-MM-DD, optional): ").strip()
            _validate_date(watched_on)
            connection = connect_db()
            try:
                connection.execute("""
                    INSERT OR IGNORE INTO Series_Progress
                    (series_id, season_number, episode_number, episode_name, watched_on)
                    VALUES (?, ?, ?, ?, ?)
                """, (series_id, season_number, episode_number, selected.get("name"), watched_on or None))
                count = connection.execute(
                    "SELECT COUNT(*) FROM Series_Progress WHERE series_id = ?", (series_id,)
                ).fetchone()[0]
                total = connection.execute(
                    "SELECT total_episodes FROM TV_Series WHERE series_id = ?", (series_id,)
                ).fetchone()[0]
                if total and count >= total:
                    connection.execute(
                        "UPDATE TV_Series SET status = 'Completed' WHERE series_id = ?", (series_id,)
                    )
                else:
                    connection.execute(
                        """UPDATE TV_Series SET status = 'Watching'
                           WHERE series_id = ? AND status = 'Plan to Watch'""", (series_id,)
                    )
                connection.commit()
                print("Episode marked as watched." if connection.total_changes else "No changes made.")
            finally:
                connection.close()
        elif action == "2":
            connection = connect_db()
            try:
                cursor = connection.execute("""
                    DELETE FROM Series_Progress
                    WHERE series_id = ? AND season_number = ? AND episode_number = ?
                """, (series_id, season_number, episode_number))
                if cursor.rowcount:
                    connection.execute(
                        """UPDATE TV_Series SET status = 'Watching'
                           WHERE series_id = ? AND status = 'Completed'""", (series_id,)
                    )
                    connection.commit()
                    print("Watched mark removed.")
                else:
                    print("That episode was not marked as watched.")
            finally:
                connection.close()
        else:
            print("Invalid action.")
    except ValueError:
        print("Enter a valid number or date.")
    except RequestException as error:
        print("TMDB API error:", error)
    except RuntimeError as error:
        print(error)


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
    print("4. Delete series and its episode progress")
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
                connection.execute("UPDATE TV_Series SET status = ? WHERE series_id = ?", (SERIES_STATUSES[selected - 1], series_id))
            elif choice == "2":
                value = input("New rating (0-10, blank to clear): ").strip()
                new_rating = float(value) if value else None
                if new_rating is not None and not 0 <= new_rating <= 10:
                    print("Rating must be between 0 and 10.")
                    return
                connection.execute("UPDATE TV_Series SET rating = ? WHERE series_id = ?", (new_rating, series_id))
            elif choice == "3":
                value = input("New notes (blank to clear): ").strip()
                connection.execute("UPDATE TV_Series SET notes = ? WHERE series_id = ?", (value or None, series_id))
            elif choice == "4":
                confirm = input(f"Delete '{name}' and all its episode progress? (y/N): ").strip().lower()
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
        print("5. View/update episode progress")
        print("6. Edit or delete series")
        print("7. Clear search and filters")
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
            print("1. Name A-Z\n2. Rating highest first\n3. First aired newest\n4. Most episodes watched")
            selected = input("Sort by: ").strip()
            sort_by = {"1": "name", "2": "rating", "3": "year", "4": "progress"}.get(selected, sort_by)
        elif choice == "5":
            value = input("Enter series ID: ").strip()
            if value.isdigit():
                match = next((r for r in rows if r[0] == int(value)), None)
                if match:
                    _show_progress(match[0], match[1])
                    update_episode_progress(match[0], match[1])
                else:
                    print("Choose a series ID visible in the current list.")
            else:
                print("Enter a valid numeric ID.")
        elif choice == "6":
            value = input("Enter series ID: ").strip()
            if value.isdigit():
                edit_series(int(value))
            else:
                print("Enter a valid numeric ID.")
        elif choice == "7":
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
                   SUM(CASE WHEN status = 'Dropped' THEN 1 ELSE 0 END),
                   (SELECT COUNT(*) FROM Series_Progress),
                   COALESCE((SELECT SUM(s.average_episode_runtime)
                             FROM Series_Progress p JOIN TV_Series s
                               ON s.series_id = p.series_id), 0)
            FROM TV_Series
        """).fetchone()
        total, plan, watching, completed, on_hold, dropped, watched_eps, watch_minutes = row
        avg_duration = connection.execute("""
            SELECT ROUND(AVG(average_episode_runtime), 1)
            FROM TV_Series WHERE average_episode_runtime IS NOT NULL
        """).fetchone()[0]
        avg_rated = connection.execute("""
            SELECT ROUND(AVG(rating), 2)
            FROM TV_Series WHERE rating IS NOT NULL
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
    print("Episodes watched:", watched_eps or 0)
    print(f"Estimated time spent watching: {(watch_minutes or 0) / 60:.1f} hours")
    print("Average episode duration across your series:", f"{avg_duration} min" if avg_duration is not None else "N/A")
    print("Average personal series rating:", avg_rated if avg_rated is not None else "N/A")
