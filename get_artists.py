from dotenv import load_dotenv
import os
import json
import base64
from requests import post, get, put
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
    url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?country=ID"
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
    
    try:
        # Fetch the currently playing track
        currently_playing = sp.currently_playing()
        if currently_playing and currently_playing.get('is_playing'):
            playing_track = currently_playing['item']
            playing_track_name = playing_track.get('name', 'Unknown')
            playing_artist_name = ', '.join(artist['name'] for artist in playing_track.get('artists', []))
            playing_album_name = playing_track.get('album', {}).get('name', 'Unknown')
            playing_track_url = playing_track.get('external_urls', {}).get('spotify', '#')
            playing_track_image = playing_track.get('album', {}).get('images', [{}])[1].get('url', 'No image available')
            currently_playing_html = f'''
            <h2>Currently Playing</h2>
            <p>Track Name: {playing_track_name}</p>
            <p>Artist: {playing_artist_name}</p>
            <p>Album: {playing_album_name}</p>
            <p>Track Link: <a href="{playing_track_url}" target="_blank">Open Track</a></p>
            <p>Track Image: <img src="{playing_track_image}" alt="Track Image" width="100"></p>
            <hr>
            '''
        else:
            currently_playing_html = '<h2>Currently Playing</h2><p>No track is currently playing.</p><hr>'

        # Fetch user's top artists
        top_artists = sp.current_user_top_artists(limit=20, offset=0, time_range='medium_term')
        artists_info = [(artist['id'], artist['name'], artist['external_urls']['spotify'], artist.get('images', [{}])[0].get('url', 'No image available')) for artist in top_artists['items']]
        artists_html = '<br>'.join([f'{name}: <a href="{url}" target="_blank">Open Artist</a> <br> <img src="{image}" alt="Artist Image" width="100">' for _, name, url, image in artists_info])
        
        # Fetch user's top tracks
        top_tracks = sp.current_user_top_tracks(limit=20, offset=0, time_range='medium_term')
        tracks_info = [(track['id'], track['name'], track['external_urls']['spotify'], track.get('album', {}).get('images', [{}])[1].get('url', 'No image available')) for track in top_tracks['items']]
        tracks_html = '<br>'.join([f'{name}: <a href="{url}" target="_blank">Open Track</a> <br> <img src="{image}" alt="Track Image" width="100">' for _, name, url, image in tracks_info])
        
        # Generate HTML
        home_html = f'''
        <h1>Home Page</h1>
        <a href="/get_playlists">Get Playlists</a><br>
        <a href="/create_playlist_form">Create Playlist</a><br>
        <form action="/search_artist" method="post">
            <label for="artist_name">Search for Artist:</label>
            <input type="text" id="artist_name" name="artist_name" required>
            <input type="submit" value="Search">
        </form><br>
        <a href="/logout">Logout</a>
        <hr>
        {currently_playing_html}
        <h2>Your Top Artists</h2>
        {artists_html}
        <hr>
        <h2>Your Top Tracks</h2>
        {tracks_html}
        '''
        
    except Exception as e:
        return f"Error fetching data: {str(e)}", 500
    
    return render_template_string(home_html)

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
        <input type="submit" value="Create Playlist">
    </form>
    <br><a href="/home">Back to Home</a>
    '''

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    token_info = cache_handler.get_cached_token()
    if not token_info:
        return redirect(sp_oauth.get_authorize_url())

    user_id = sp.current_user()['id']
    playlist_name = request.form.get('name')
    description = request.form.get('description', '')

    if not playlist_name:
        return jsonify({"error": "Playlist name is required"}), 400

    try:
        # Create playlist
        playlist = sp.user_playlist_create(
            user=user_id,
            name=playlist_name,
            public=True,  # Always public
            collaborative=False,  # Always non-collaborative
            description=description
        )
        
        playlist_id = playlist['id']
        playlist_url = playlist['external_urls']['spotify']

        # Fetch top tracks
        top_tracks = sp.current_user_top_tracks(limit=20, offset=0, time_range='medium_term')
        track_ids = [track['id'] for track in top_tracks['items']]

        # Fetch top tracks from top artists
        top_artists = sp.current_user_top_artists(limit=5, offset=0, time_range='medium_term')
        for artist in top_artists['items']:
            artist_id = artist['id']
            artist_top_tracks = sp.artist_top_tracks(artist_id, country='ID')
            track_ids.extend([track['id'] for track in artist_top_tracks['tracks']])

        # Add tracks to the newly created playlist
        sp.user_playlist_add_tracks(user_id, playlist_id, track_ids)

        return f'''
        <h1>Playlist Created Successfully</h1>
        <p>Your new playlist has been created and tracks have been added.</p>
        <p>View your playlist here: <a href="{playlist_url}" target="_blank">Open Playlist</a></p>
        <br><a href="/home">Back to Home</a>
        '''
    except Exception as e:
        return f"Error creating playlist: {str(e)}", 500





@app.route('/search_artist', methods=['POST'])
def search_artist():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return redirect(sp_oauth.get_authorize_url())

    artist_name = request.form.get('artist_name')
    token = get_token()
    result = search_artists_id(token, artist_name)
    if not result:
        return "Artist not found."

    artist_id = result['id']
    artist_image = result.get('images', [{}])[0].get('url', 'No image available')
    artist_link = result['external_urls']['spotify']
    artist_name = result['name']
    
    try:
        songs = get_songs_of_artist(token, artist_id)
        songs_html = '<br>'.join([f'{song["name"]}: <a href="{song["external_urls"]["spotify"]}" target="_blank">Open Song</a>' for song in songs])
    except Exception as e:
        songs_html = f"Error fetching songs: {str(e)}"

    return f'''
    <h1>Artist: {artist_name}</h1>
    <p><a href="{artist_link}" target="_blank">Open Artist</a></p>
    <p><img src="{artist_image}" alt="Artist Image" width="100"></p>
    <h2>Top Songs</h2>
    {songs_html}
    <br><a href="/home">Back to Home</a>
    '''

@app.route('/logout')
def logout():
    session.clear()  
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
