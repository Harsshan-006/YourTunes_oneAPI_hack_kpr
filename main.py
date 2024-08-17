import os
from dotenv import load_dotenv

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler

from flask import Flask, session, redirect, url_for, request, jsonify

load_dotenv()
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)

redirect_uri = 'http://localhost:5000/callback'
scope = "playlist-read-private, user-modify-playback-state, user-read-playback-state, playlist-modify-private, playlist-modify-public, user-top-read"

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True
)

sp = Spotify(auth_manager=sp_oauth)

@app.route('/')
def home():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    return redirect(url_for("get_playlists"))

@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(url_for('get_playlists'))

@app.route('/get_playlists')
def get_playlists():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    playlists = sp.current_user_playlists()
    playlists_info = [(pl['name'], pl['external_urls']['spotify']) for pl in playlists['items']]
    playlists_html = '<br>'.join([f'{name}: <a href="{url}" target="_blank">Open Playlist</a>' for name, url in playlists_info])
    
    # HTML for creating a new playlist
    create_playlist_form = '''
    <h2>Create a New Playlist</h2>
    <form action="/create_playlist" method="post">
        <label for="name">Playlist Name:</label>
        <input type="text" id="name" name="name" required>
        <br>
        <label for="description">Description:</label>
        <input type="text" id="description" name="description">
        <br>
        <label for="public">Public:</label>
        <input type="checkbox" id="public" name="public" checked>
        <br>
        <input type="submit" value="Create Playlist">
    </form>
    '''
    
    return playlists_html + create_playlist_form


@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    user_id = sp.current_user()['id']
    playlist_name = request.form.get('name')
    public = request.form.get('public') == 'on'  
    description = request.form.get('description', '')

    if not playlist_name:
        return jsonify({"error": "Playlist name is required"}), 400

    playlist = sp.user_playlist_create(user_id, playlist_name, public=public, description=description)
    return jsonify(playlist), 201


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)
