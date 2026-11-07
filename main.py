from database import create_tables
from movies import (
    add_movie,
    get_watched_movies,
    get_watchlist_movies,
    show_statistics
)
from import_movies import import_movies_from_csv
from series import (
    add_series,
    browse_series,
    show_series_statistics
)


def main():

    create_tables()

    while True:

        print("\n========== CINETRACK ==========")
        print("1. Add a movie")
        print("2. Watched movies")
        print("3. Movies to watch next")
        print("4. Import movies from CSV")
        print("5. Movie statistics")
        print("6. Add a TV series")
        print("7. Browse TV series")
        print("8. TV series statistics")
        print("0. Exit")

        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            add_movie()

        elif choice == "2":
            get_watched_movies()

        elif choice == "3":
            get_watchlist_movies()

        elif choice == "4":
            import_movies_from_csv()

        elif choice == "5":
            show_statistics()

        elif choice == "6":
            add_series()

        elif choice == "7":
            browse_series()

        elif choice == "8":
            show_series_statistics()

        elif choice == "0":
            print("Goodbye!")
            break

        else:
            print("Invalid choice!")


if __name__ == "__main__":
    main()
