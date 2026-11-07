
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"


def search_movies(query):

    url = f"{BASE_URL}/search/movie"

    params = {
        "api_key": API_KEY,
        "query": query
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    return response.json()["results"]


def get_movie_details(movie_id):

    url = f"{BASE_URL}/movie/{movie_id}"

    params = {
        "api_key": API_KEY,
        "append_to_response": "credits"
    }

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()

    return response.json()
