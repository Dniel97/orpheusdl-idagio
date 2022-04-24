from datetime import timedelta, datetime
from os import urandom

from utils.utils import create_requests_session


class IdagioApi:
    def __init__(self):
        self.API_URL = 'https://api.idagio.com/'

        self.device_id = None
        self.access_token = None
        self.expires = None

        # required for the cookies
        self.s = create_requests_session()

    def headers(self, use_access_token: bool = False):
        return {
            'User-Agent': 'Android 3.3.0 (Build 3030000) [release]',
            'Authorization': f'Bearer {self.access_token}' if use_access_token else None,
            'X-Client': 'android',
            'X-Client-Version': '3.3.0',
            'X-Device-ID': self.device_id,
            'X-Device-Class': 'PHONE'
        }

    def auth(self, username: str, password: str) -> dict:
        # generate a device id
        self.device_id = urandom(8).hex()

        r = self.s.post(f'{self.API_URL}v2.1/oauth', data={
            'client_id': 'com.idagio.app.android',
            'client_secret': 'adbisIGrocsUckWyodUj2knedpyepubGurlyeawosShyufJishleseanreBlogIbCefHodCigNafweegyeebraft'
                             'EdnooshDeavolirdoppEcIassyet9CirIrnofmaj',
            'username': username,
            'password': password,
            'grant_type': 'password',
        })

        if r.status_code != 200:
            return r.json()

        # convert to JSON
        r = r.json()

        # save all tokens with access_token expiry date
        self.access_token = r['access_token']
        self.expires = datetime.now() + timedelta(seconds=r['expires_in'])

        return r

    def set_session(self, session: dict):
        self.access_token = session.get('access_token')
        self.device_id = session.get('device_id')
        self.expires = session.get('expires')

    def get_session(self):
        return {
            'access_token': self.access_token,
            'device_id': self.device_id,
            'expires': self.expires
        }

    def _get(self, endpoint: str, params: dict = None):
        # function for API requests
        if not params:
            params = {}

        r = self.s.get(f'{self.API_URL}{endpoint}', params=params, headers=self.headers(use_access_token=True))

        # access_token expired
        if r.status_code == 401:
            raise ValueError(r.text)

        if r.status_code not in {200, 201, 202}:
            raise ConnectionError(r.text)

        return r.json()

    def get_account(self):
        return self._get('v2.1/user')

    def get_search(self, query: str):
        return self._get('v1.8/lucene/search', params={
            'term': query,
            'full': True
        })

    def get_recording(self, recording_id: str):
        return self._get(f'v2.0/metadata/recordings/{recording_id}').get('result')

    def get_album(self, album_id: str):
        return self._get(f'v2.0/metadata/albums/{album_id}').get('result')

    def get_playlist(self, playlist_id: str):
        return self._get(f'v2.0/playlists/{playlist_id}').get('result')

    def get_artist(self, artist_id: str):
        return self._get(f'artists.v3/{artist_id}').get('result')

    def get_artist_albums(self, artist_id: str, cursor: str = None, limit: int = 100):
        return self._get(f'v2.0/metadata/albums/filter', params={
            'artist': artist_id,
            'sort': 'copyrightYear',
            'limit': limit,
            'cursor': cursor
        })

    def get_artist_recordings(self, artist_id: str, cursor: str = None, limit: int = 100):
        return self._get(f'v2.0/metadata/recordings/filter', params={
            'artist': artist_id,
            'sort': 'chronological',
            'limit': limit,
            'cursor': cursor
        })

    def get_artist_works(self, artist_id: str, cursor: str = None, limit: int = 100):
        return self._get(f'v2.0/metadata/works/filter', params={
            'artist': artist_id,
            'limit': limit,
            'cursor': cursor
        })

    def get_search(self, query: str):
        return self._get('v1.8/lucene/search', params={
            'term': query,
            'full': True
        })

    def get_track_stream_2(self, track_id: str, quality: int = 90):
        # unencrypted sonos endpoint only for quality = 90 (FLAC).
        r = self.s.get(f'{self.API_URL}v1.8/content/track/{track_id}', params={
            'quality': quality,
            'format': 2,
            'client_type': 'sonos-2',
            'client_version': '17.2.4',
            'device_id': 'web'
        }, headers=self.headers(use_access_token=True))

        if r.status_code != 200:
            raise ConnectionError(r.text)

        return [r.json()]

    def get_track_stream(self, track_id: str, quality: int = 90):
        # quality is either 50 (160 kbit/s AAC), 70 (320 kbit/s AAC) or 90 (FLAC).
        r = self.s.post(f'{self.API_URL}v2.0/streams/bulk', params={
            'quality': quality,
            'client_type': 'android-3',
            'client_version': '3.3.0',
            'device_id': self.device_id
        }, json={"ids": [track_id]}, headers=self.headers(use_access_token=True))

        if r.status_code != 200:
            raise ConnectionError(r.text)

        return r.json().get('results')
