from tmdb import search_movies, get_movie_details

results = search_movies("Interstellar")

for movie in results[:5]:
    print(
        movie["id"],
        movie["title"],
        movie["release_date"]
    )

movie = get_movie_details(157336)

print(movie["title"])
print(movie["runtime"])
print(movie["genres"])

directors = [
    person["name"]
    for person in movie["credits"]["crew"]
    if person["job"] == "Director"
]

print("Directors:", directors)