from dotenv import load_dotenv
import os
import json
import base64
from requests import post, get
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from flask import Flask, session, redirect, url_for, request, jsonify, render_template_string

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

def get_token():
    auth_string = client_id + ":" + client_secret
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")

    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": "Basic " + auth_base64,
        "Content-type": "application/x-www-form-urlencoded"
    }

    data = {"grant_type": "client_credentials"}
    result = post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result["access_token"]
    return token

def get_auth_header(token):
    return {"Authorization": "Bearer " + token}

def search_artists_id(token, artist_name):
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    query = f"?q={artist_name}&type=artist&limit=1"
    query_url = url + query
    result = get(query_url, headers=headers)
    json_result = json.loads(result.content)["artists"]["items"]
    if not json_result:
        return None
    return json_result[0]

def get_songs_of_artist(token, artist_id):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?country=IN"
    headers = get_auth_header(token)
    result = get(url, headers=headers)
    json_result = json.loads(result.content)["tracks"]
    return json_result

@app.route('/')
def login():
    return '''
    <h1>Login Page</h1>
    <a href="/home">Login with Spotify</a>
    '''

@app.route('/home')
def home():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return redirect(sp_oauth.get_authorize_url())
    
    return '''
    <h1>Home Page</h1>
    <a href="/get_playlists">Get Playlists</a><br>
    <a href="/create_playlist_form">Create Playlist</a><br>
    <form action="/search_artist" method="post">
        <label for="artist_name">Search for Artist:</label>
        <input type="text" id="artist_name" name="artist_name" required>
        <input type="submit" value="Search">
    </form><br>
    <a href="/logout">Logout</a>
    '''

@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(url_for('home'))

@app.route('/get_playlists')
def get_playlists():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return redirect(sp_oauth.get_authorize_url())
    
    try:
        playlists = sp.current_user_playlists()
        playlists_info = [(pl['name'], pl['external_urls']['spotify']) for pl in playlists['items']]
        playlists_html = '<br>'.join([f'{name}: <a href="{url}" target="_blank">Open Playlist</a>' for name, url in playlists_info])
    except Exception as e:
        return f"Error fetching playlists: {str(e)}", 500
    
    return f'''
    <h1>Your Playlists</h1>
    {playlists_html}
    <br><a href="/home">Back to Home</a>
    '''

@app.route('/create_playlist_form')
def create_playlist_form():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return redirect(sp_oauth.get_authorize_url())
    
    return '''
    <h1>Create a New Playlist</h1>
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
    <br><a href="/home">Back to Home</a>
    '''

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return redirect(sp_oauth.get_authorize_url())
    
    user_id = sp.current_user()['id']
    playlist_name = request.form.get('name')
    public = request.form.get('public') == 'on'
    description = request.form.get('description', '')

    if not playlist_name:
        return jsonify({"error": "Playlist name is required"}), 400

    playlist = sp.user_playlist_create(user_id, playlist_name, public=public, description=description)
    return jsonify(playlist), 201

@app.route('/search_artist', methods=['POST'])
def search_artist():
    artist_name = request.form.get('artist_name')
    token = get_token()
    result = search_artists_id(token, artist_name)
    if not result:
        return "No artist found", 404
    
    artist_id = result["id"]
    artist_image = result.get('images', [{}])[0].get('url', 'No image available')
    songs = get_songs_of_artist(token, artist_id)
    
    artist_info_html = f'''
    <h2>Artist Information</h2>
    <p>Artist Name: {result.get('name', 'Unknown')}</p>
    <p>Artist Image: <img src="{artist_image}" alt="Artist Image" width="200"></p>
    <hr>
    '''
    
    songs_html = '<h2>Top Songs</h2>'
    for song in songs:
        song_name = song.get('name', 'Unknown')
        song_id = song.get('id', 'Unknown')
        song_link = song.get('external_urls', {}).get('spotify', 'Unknown')
        image_url = song.get('album', {}).get('images', [{}])[1].get('url', 'No image available')

        songs_html += f'''
        <div>
            <p>Song Name: {song_name}</p>
            <p>Song ID: {song_id}</p>
            <p>Song Link: <a href="{song_link}" target="_blank">Open Song</a></p>
            <p>Song Image: <img src="{image_url}" alt="Song Image" width="100"></p>
            <hr>
        </div>
        '''
    
    return render_template_string(artist_info_html + songs_html)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)
