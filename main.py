import os
from dotenv import load_dotenv

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler

from flask import Flask, session

app = Flask(__name__)
app.config['SECRET_KEY'] = os.unrandom(64)

redirect_uri = 'https://localhost:5000/callback'
scope = "user-read-playback-state, user-modify-playback-state, playlist-read-private, playlist-modify-private, playlist-modify-public, user-top-read"

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(


)

if __name__ == "__main__":
    app.run(debug=True)