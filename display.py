
from rich.console import Console
from rich.table import Table

console = Console()


def display_movies(movies, title):
    if not movies:
        console.print("\n[yellow]No movies found in your collection.[/yellow]")
        return

    table = Table(title=f"🎬 {title} Movies")

    table.add_column("ID", justify="center")
    table.add_column("Movie", style="cyan")
    table.add_column("Year", justify="center")
    table.add_column("Director")
    table.add_column("Runtime", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Rating", justify="center")
    table.add_column("Notes")

    for movie in movies:

        movie_id, title, year, runtime, status, rating, notes, directors = movie

        director_names = ", ".join(directors) if directors else "Unknown"

        runtime_text = f"{runtime} min" if runtime else "N/A"
        rating_text = f"{rating}/10" if rating is not None else "Not rated"
        notes_text = notes if notes else "None"

        table.add_row(
            str(movie_id),
            title,
            str(year or "N/A"),
            director_names,
            runtime_text,
            status,
            rating_text,
            notes_text
        )

    console.print(table)
