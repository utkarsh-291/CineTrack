import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"


def _get(endpoint, params=None):
    if not API_KEY:
        raise RuntimeError("TMDB_API_KEY is missing. Add it to your .env file.")

    request_params = {"api_key": API_KEY}
    if params:
        request_params.update(params)

    response = requests.get(
        f"{BASE_URL}{endpoint}",
        params=request_params,
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def search_movies(query):
    return _get("/search/movie", {"query": query})["results"]


def get_movie_details(movie_id):
    return _get(f"/movie/{movie_id}", {"append_to_response": "credits"})


def search_tv(query):
    return _get("/search/tv", {"query": query})["results"]


def get_tv_details(series_id):
    return _get(f"/tv/{series_id}")


def get_tv_season_details(series_id, season_number):
    return _get(f"/tv/{series_id}/season/{season_number}")
