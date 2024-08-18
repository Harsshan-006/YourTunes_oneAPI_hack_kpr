from dotenv import load_dotenv
import os
import json
import base64
from requests import post, get
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from flask import Flask, session, redirect, url_for, request, jsonify, render_template

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

def search_song_id(token, song_name):
    url = "https://api.spotify.com/v1/search"
    headers = get_auth_header(token)
    query = f"?q={song_name}&type=track&limit=1"
    query_url = url + query
    result = get(query_url, headers=headers)
    json_result = json.loads(result.content)
    tracks = json_result.get("tracks", {}).get("items", [])
    if not tracks:
        return None
    return tracks[0]

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
    return render_template('login.html')

@app.route('/home')
def home():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return redirect(sp_oauth.get_authorize_url())

    try:
        # Fetch the currently playing track
        currently_playing = sp.current_playback()
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

        return render_template('home.html', currently_playing_html=currently_playing_html, artists_html=artists_html, tracks_html=tracks_html)

    except Exception as e:
        print(f"Error: {e}")
        return redirect(url_for('login'))

@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(url_for('home'))

@app.route('/get_playlists')
def get_playlists():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return redirect(sp_oauth.get_authorize_url())
    
    playlists = sp.current_user_playlists()
    playlists_info = [(playlist['name'], playlist['external_urls']['spotify']) for playlist in playlists['items']]
    playlists_html = '<br>'.join([f'{name}: <a href="{url}" target="_blank">Open Playlist</a>' for name, url in playlists_info])
    
    return render_template('playlists.html', playlists_html=playlists_html)

@app.route('/create_playlist_form')
def create_playlist_form():
    return render_template('create_playlist_form.html')

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return redirect(sp_oauth.get_authorize_url())
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    sp.user_playlist_create(user=sp.current_user()['id'], name=name, description=description, public=True, collaborative=False)
    
    return redirect(url_for('home'))

@app.route('/search_artist', methods=['POST'])
def search_artist():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        return redirect(sp_oauth.get_authorize_url())
    
    artist_name = request.form.get('artist_name')
    token = get_token()
    artist = search_artists_id(token, artist_name)
    
    if not artist:
        return "Artist not found"
    
    artist_id = artist['id']
    artist_name = artist['name']
    artist_url = artist['external_urls']['spotify']
    artist_image = artist.get('images', [{}])[1].get('url', 'No image available')
    top_tracks = get_songs_of_artist(token, artist_id)
    
    top_tracks_info = [(track['name'], track['external_urls']['spotify'], track.get('album', {}).get('images', [{}])[1].get('url', 'No image available')) for track in top_tracks]
    top_tracks_html = '<br>'.join([f'{name}: <a href="{url}" target="_blank">Open Track</a> <br> <img src="{image}" alt="Track Image" width="100">' for name, url, image in top_tracks_info])
    
    related_artists_info = artist.get('genres', [])
    related_artists_html = '<br>'.join([f'Genre: {genre}' for genre in related_artists_info])
    
    return render_template('artist.html', artist_name=artist_name, artist_url=artist_url, artist_image=artist_image, top_tracks_html=top_tracks_html, related_artists_html=related_artists_html)

@app.route('/search_song', methods=['POST'])
def search_song_route():
    token = get_token()
    song_name = request.form.get('song_name')
    song = search_song_id(token, song_name)
    
    if song is None:
        return jsonify({"error": "Song not found"}), 404

    song_name = song['name']
    song_url = song['external_urls']['spotify']
    song_image = song.get('album', {}).get('images', [{}])[1].get('url', 'No image available')
    artist_name = ', '.join(artist['name'] for artist in song.get('artists', []))
    album_name = song.get('album', {}).get('name', 'Unknown')

    # Fetch related artists for the song's artists
    try:
        related_artists_html = ''
        for artist in song['artists']:
            artist_id = artist['id']
            related_artists = sp.artist_related_artists(artist_id)['artists']
            related_artists_html += f'<h3>Related Artists to {artist["name"]}</h3>'
            related_artists_html += '<br>'.join([
                f'{related_artist["name"]}: <a href="{related_artist["external_urls"]["spotify"]}" target="_blank">Open Artist</a> <br> <img src="{related_artist.get("images", [{}])[0].get("url", "No image available")}" alt="Artist Image" width="100">'
                for related_artist in related_artists
            ])
    except Exception as e:
        related_artists_html = f"Error fetching related artists: {str(e)}"

    return render_template('search_song.html',
                           song_name=song_name,
                           artist_name=artist_name,
                           album_name=album_name,
                           song_url=song_url,
                           song_image=song_image,
                           related_artists_html=related_artists_html)


@app.route('/logout')
def logout():
    sp_oauth.revoke_token(cache_handler.get_cached_token())
    cache_handler.clear_cache()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)


@app.route('/test')
def test():
    return render_template('test.html', message="Hello, this is a test!")