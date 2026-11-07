
import csv

from tmdb import search_movies, get_movie_details
from movies import save_movie
from requests.exceptions import RequestException

def read_movies_from_csv():

    with open("movies.csv", "r", encoding="utf-8-sig", newline="") as file:

        reader = csv.DictReader(file)

        movies = list(reader)

    return movies


def validate_movie(movie):

    title = movie.get("title", "").strip()

    if not title:
        return False, "Movie title is missing."

    status = movie.get("status", "").strip().title()

    if status not in ["Watched", "Watchlist"]:
        return False, "Invalid status."

    rating = movie.get("rating", "").strip()

    if rating:
        try:
            rating = float(rating)
        except ValueError:
            return False, "Rating must be a number."

        if not 0 <= rating <= 10:
            return False, "Rating must be between 0 and 10."

    release_year = movie.get("release_year", "").strip()

    if release_year:
        if not release_year.isdigit() or len(release_year) != 4:
            return False, "Invalid release year."

    date_watched = movie.get("date_watched", "").strip()

    if date_watched and status != "Watched":
        return False, "Watchlist movies cannot have a watched date."

    return True, "Valid"


def select_tmdb_movie(movie):

    title = movie["title"].strip()
    release_year = movie.get("release_year", "").strip()

    results = search_movies(title)

    if not results:
        print(f"\nNo TMDB results found for: {title}")
        return None

    # Filter results using release year, if provided.
    if release_year:

        matching_results = [
            result for result in results
            if result.get("release_date", "").startswith(release_year)
        ]

        if matching_results:
            results = matching_results
        else:
            print(f"\nNo exact year match found for {title} ({release_year}).")
            print("Showing other search results instead.")

    results = results[:10]

    # Automatically select if there is exactly one matching result.
    if release_year and len(results) == 1:
        selected = results[0]
        print(f"\nMatched: {selected['title']} ({release_year})")
        return selected

    print(f"\nSearch results for: {title}\n")

    for index, result in enumerate(results, start=1):

        year = result.get("release_date", "")[:4] or "Unknown"

        print(f"{index}. {result['title']} ({year})")

    print("0. Skip this movie")

    try:
        choice = int(input("\nSelect the correct movie: "))

        if choice == 0:
            return None

        if choice < 1 or choice > len(results):
            print("Invalid selection.")
            return None

        return results[choice - 1]

    except ValueError:
        print("Please enter a valid number.")
        return None


def import_movies_from_csv():

    movies = read_movies_from_csv()

    if not movies:
        print("No movies found in CSV file.")
        return

    imported = 0
    skipped = 0
    failed = 0

    for index, movie in enumerate(movies, start=1):

        title = movie.get("title", "").strip()

        print(f"\n[{index}/{len(movies)}] Processing: {title}")

        # Step 1: Validate CSV data
        is_valid, message = validate_movie(movie)

        if not is_valid:
            print("Invalid entry:", message)
            failed += 1
            continue

        try:
            # Step 2: Find the movie on TMDB
            selected = select_tmdb_movie(movie)

            if selected is None:
                skipped += 1
                continue

            # Step 3: Fetch complete movie details
            details = get_movie_details(selected["id"])

            # Step 4: Convert CSV values
            status = movie["status"].strip().title()

            rating_input = movie.get("rating", "").strip()
            rating = float(rating_input) if rating_input else None

            date_watched = movie.get("date_watched", "").strip()
            notes = movie.get("notes", "").strip()

            # Step 5: Save using existing function
            result = save_movie(
                details,
                status,
                rating,
                date_watched,
                notes
            )

            if result == "inserted":
                imported += 1
            elif result == "duplicate":
                skipped += 1
            else:
                failed += 1

        except RequestException as e:
            print("TMDB API error:", e)
            failed += 1

    print("\n========== IMPORT SUMMARY ==========")
    print("Total movies:", len(movies))
    print("Processed successfully:", imported)
    print("Skipped:", skipped)
    print("Failed:", failed)

if __name__ == "__main__":
    import_movies_from_csv()