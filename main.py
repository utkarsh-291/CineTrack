from database import create_tables
from movies import add_movie, get_all_movies


def main():

    create_tables()

    while True:

        print("\n========== CINETRACK ==========")
        print("1. Add a movie")
        print("2. View all movies")
        print("0. Exit")

        choice = input("\nEnter choice: ")

        if choice == "1":
            add_movie()

        elif choice == "2":
            get_all_movies()

        elif choice == "0":
            print("Goodbye!")
            break

        else:
            print("Invalid choice!")


if __name__ == "__main__":
    main()