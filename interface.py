import logging
import re
from urllib.parse import urlparse

from Cryptodome.Cipher import AES
from Cryptodome.Hash import SHA256
from tqdm import tqdm

from utils.models import *
from utils.utils import create_temp_filename, silentremove, sanitise_name
from .idagio_api import IdagioApi

module_information = ModuleInformation(
    service_name='Idagio',
    module_supported_modes=ModuleModes.download | ModuleModes.covers | ModuleModes.credits,
    session_settings={'username': '', 'password': ''},
    session_storage_variables=['device_id', 'access_token', 'expires'],
    netlocation_constant='idagio',
    url_decoding=ManualEnum.manual,
    test_url='https://app.idagio.com/de/recordings/41598968'
)


class ModuleInterface:
    # noinspection PyTypeChecker
    def __init__(self, module_controller: ModuleController):
        self.exception = module_controller.module_error
        self.oprinter = module_controller.printer_controller
        self.print = module_controller.printer_controller.oprint
        self.module_controller = module_controller
        self.disable_subscription_check = module_controller.orpheus_options.disable_subscription_check

        # LOW = 160kbit/s AAC, MEDIUM = 320kbit/s AAC, LOSSLESS = FLAC
        self.quality_parse = {
            QualityEnum.MINIMUM: 50,
            QualityEnum.LOW: 50,
            QualityEnum.MEDIUM: 70,
            QualityEnum.HIGH: 70,
            QualityEnum.LOSSLESS: 90,
            QualityEnum.HIFI: 90
        }

        self.session = IdagioApi()
        session = {
            'access_token': module_controller.temporary_settings_controller.read('access_token'),
            'device_id': module_controller.temporary_settings_controller.read('device_id'),
            'expires': module_controller.temporary_settings_controller.read('expires')
        }

        self.session.set_session(session)
        if session['access_token'] and session['device_id'] and session['expires']:
            if not self.valid_account():
                self.exception('You need a Premium subscription.')

    def login(self, email: str, password: str):
        logging.debug(f'Idagio: no session found, login')
        login_data = self.session.auth(email, password)

        if login_data.get('error_description') is not None:
            raise self.exception(login_data.get('error_description'))

        if not self.valid_account():
            self.exception('You need a Premium subscription.')

        # save the new access_token, refresh_token and expires in the temporary settings
        self.module_controller.temporary_settings_controller.set('access_token', self.session.access_token)
        self.module_controller.temporary_settings_controller.set('device_id', self.session.device_id)
        self.module_controller.temporary_settings_controller.set('expires', self.session.expires)

    def valid_account(self):
        # get the subscription from the API and check if it's at least a "Premium" subscription
        if not self.disable_subscription_check:
            account_data = self.session.get_account()
            return account_data.get('premium')
        return True

    def custom_url_parse(self, link: str):
        link = re.sub(r'/[a-z]{2}/', '/', link)
        url = urlparse(link)
        components = url.path.split('/')

        if not components or len(components) <= 2:
            raise self.exception(f'Invalid URL: {link}')

        if len(components) in {3, 4}:
            type_ = components[1]
            media_id = components[2]
        else:
            raise self.exception(f'Invalid URL: {link}')

        if type_ == 'recordings':
            media_type = DownloadTypeEnum.track
        elif type_ == 'albums':
            media_type = DownloadTypeEnum.album
        elif type_ == 'playlists':
            media_type = DownloadTypeEnum.playlist
        elif type_ == 'profiles':
            media_type = DownloadTypeEnum.artist
        else:
            raise self.exception(f'{type_} not supported!')

        return MediaIdentification(
            media_type=media_type,
            media_id=media_id
        )

    def search(self, query_type: DownloadTypeEnum, query: str, track_info: TrackInfo = None, limit: int = 20):
        results = self.session.get_search(query)

        items = []
        # TODO: sort artists by popularity
        if query_type is DownloadTypeEnum.artist:
            # get all persons and ensembles
            for i in results.get('artists').get('persons') + results.get('artists').get('ensembles'):
                items.append(SearchResult(
                    name=i.get('name'),
                    result_id=i.get('id'),
                    additional=[i.get('functions')[0].title()]
                ))
        elif query_type is DownloadTypeEnum.album:
            for i in results.get('albums', []):
                items.append(SearchResult(
                    name=i.get('title'),
                    artists=[a.get('name') for a in i.get('participants')],
                    result_id=i.get('id'),
                    additional=[i.get('upc')]
                ))
        elif query_type is DownloadTypeEnum.track:
            # add all pieces
            for i in results.get('music').get('pieces'):
                items.append(SearchResult(
                    name=i.get('title').get('title'),
                    artists=[c.get('name') for c in i.get('workpart').get('work').get('composers')],
                    result_id=i.get('workpart').get('work').get('defaultRecordingId'),
                ))
            # add all works
            for i in results.get('music').get('works'):
                items.append(SearchResult(
                    name=i.get('title').get('title'),
                    artists=[c.get('name') for c in i.get('composers')],
                    result_id=i.get('defaultRecordingId'),
                ))
            # TODO: add all recordings
        elif query_type is DownloadTypeEnum.playlist:
            for i in results.get('playlists'):
                items.append(SearchResult(
                    name=i.get('title'),
                    artists=[i.get('curatorName')] if i.get('curatorName') != '' else 'Unknown',
                    result_id=i.get('id'),
                ))
        else:
            raise self.exception(f'Query type "{query_type.name}" is not supported!')

        return items

    def get_playlist_info(self, playlist_id: str) -> PlaylistInfo:
        playlist_data = self.session.get_playlist(playlist_id)

        return PlaylistInfo(
            name=playlist_data.get('title'),
            creator=playlist_data.get('curator').get('name'),
            tracks=[t.get('recording').get('id') for t in playlist_data.get('tracks')],
            # TODO: remove mandatory release year
            release_year=2022,
            cover_url=playlist_data.get('imageUrl'),
            description=playlist_data.get('description'),
        )

    def get_artist_info(self, artist_slug: str, get_credited_albums: bool) -> ArtistInfo:
        artist_data = self.session.get_artist(artist_slug)
        artist_id = artist_data.get('id')

        # get the first 100 albums from the artist
        artist_albums_data = self.session.get_artist_albums(artist_id)
        # add those albums to artist_albums
        artist_albums = artist_albums_data.get('results')
        # get the next page(s) of albums and add them to artist_albums
        total_albums = artist_albums_data.get('meta').get('count')
        while artist_albums_data.get('meta').get('cursor').get('next'):
            print(f'Fetching {len(artist_albums)}/{total_albums} albums', end='\r')
            artist_albums_data = self.session.get_artist_albums(
                artist_id,
                cursor=artist_albums_data.get('meta').get('cursor').get('next'),
            )
            artist_albums += artist_albums_data.get('results')

        # get the first 100 tracks from the artist
        artist_tracks_data = self.session.get_artist_recordings(artist_id)
        # add those tracks to artist_tracks
        artist_tracks = artist_tracks_data.get('results')
        # get the next page(s) of tracks and add them to artist_tracks
        total_tracks = artist_tracks_data.get('meta').get('count')
        while artist_tracks_data.get('meta').get('cursor').get('next'):
            print(f'Fetching {len(artist_tracks)}/{total_tracks} tracks', end='\r')
            artist_tracks_data = self.session.get_artist_recordings(
                artist_id,
                cursor=artist_tracks_data.get('meta').get('cursor').get('next'),
            )
            artist_tracks += artist_tracks_data.get('results')

        return ArtistInfo(
            name=artist_data.get('name'),
            albums=[a.get('id') for a in artist_albums],
            tracks=[t.get('id') for t in artist_tracks],
        )

    def get_album_info(self, album_id: str, data=None) -> AlbumInfo:
        # check if album is already in album cache, add it
        if data is None:
            data = {}

        album_data = data.get(album_id) if album_id in data else self.session.get_album(album_id)
        tracks = album_data.get('tracks')

        # cache the album_data for the track_info
        cache = {'data': {album_data.get('id'): album_data}}

        # get the first composer as an album artist
        album_artist = [c for c in album_data.get('participants') if c.get('type') == 'composer'][0]

        return AlbumInfo(
            name=album_data.get('title'),
            # use copyrightYear instead of publishDate?
            release_year=album_data.get('publishDate')[:4] if album_data.get('publishDate') else None,
            upc=album_data.get('upc'),
            cover_url=album_data.get('imageUrl'),
            # always use first participant?
            artist=album_artist.get('name'),
            artist_id=album_artist.get('id'),
            tracks=[t.get('recording').get('id') for t in tracks],
            booklet_url=album_data.get('bookletUrl'),
            track_extra_kwargs=cache
        )

    def get_track_info(self, recording_id: str, quality_tier: QualityEnum, codec_options: CodecOptions,
                       data=None) -> TrackInfo:
        if data is None:
            data = {}

        quality_tier = self.quality_parse[quality_tier]

        track_data = data[recording_id] if recording_id in data else self.session.get_recording(recording_id)
        # track_is is just needed for the track_extra_kwargs
        track_id = track_data.get('tracks')[0].get('id')

        album_id = track_data.get('albums')[0]
        album_data = data[album_id] if album_id in data else self.session.get_album(album_id)

        # also add a LIVE tag to the track if it's a live track?
        track_name = track_data.get('work').get('title')

        release_year = track_data.get('recordingDate').get('from')
        genres = [track_data.get('work').get('genre').get('title')] if track_data.get('work').get('genre') else []
        # check if a second genre exists
        genres += [track_data.get('work').get('subgenre').get('title')] if track_data.get('work').get(
            'subgenre') else []

        error = None
        if track_data['geoblocked']:
            error = f'Track "{track_data.get("name")}" is blocked in your region!'

        bitrate = {
            '50': 160,
            '70': 320,
            '90': 1411
        }[str(quality_tier)]

        # iterate over all album tracks and search the index with the same track id
        track_number = 1
        for i, track in enumerate(album_data.get('tracks')):
            if track.get('id') == track_id:
                track_number = i + 1
                break

        extra_tags = {}
        # add the tonality (key) to the extra_tags
        if track_data.get('work').get('tonality'):
            extra_tags['Key'] = track_data.get('work').get('tonality').get('title')
        # add the epoch to the extra_tags
        if track_data.get('work').get('epoch'):
            extra_tags['Epoch'] = track_data.get('work').get('epoch').get('title')

        tags = Tags(
            album_artist=album_data.get('participants')[0].get('name'),
            track_number=track_number,
            total_tracks=len(album_data.get('tracks')),
            # just an assumption
            disc_number=1,
            total_discs=1,
            upc=album_data.get('upc'),
            genres=genres if genres != [] else None,
            release_date=track_data.get('publishDate') if track_data.get('publishDate') else None,
            copyright=f'©℗ {album_data.get("copyright")}',
            extra_tags=extra_tags
        )

        track_info = TrackInfo(
            name=track_name,
            album=album_data.get('title'),
            album_id=album_data.get('id'),
            artists=[a for a in track_data.get('summary').split(', ')],
            artist_id=track_data.get('work').get('composer').get('id'),
            release_year=release_year,
            bitrate=bitrate,
            # https://en.wikipedia.org/wiki/Audio_bit_depth#cite_ref-1
            bit_depth=16 if quality_tier == 90 else None,
            cover_url=album_data.get('imageUrl'),
            tags=tags,
            codec=CodecEnum.FLAC if quality_tier == 90 else CodecEnum.AAC,
            download_extra_kwargs={'track_id': track_id, 'quality_tier': quality_tier},
            credits_extra_kwargs={'data': {recording_id: track_data}},
            error=error
        )

        return track_info

    def get_track_credits(self, track_id: str, data=None) -> Optional[list]:
        if data is None:
            data = {}

        track_data = data.get(track_id) if data.get(track_id) else self.session.get_recording(track_id)

        credits_dict = {}
        # add the track composer to credits_dict
        # credits_dict = {'Composer': [track_data.get('work').get('composer').get('name')]}

        # add all soloists to credits
        for soloist in track_data.get('soloists'):
            # check if the dict contains no list, create one
            if not credits_dict.get(soloist.get('instrument').get('title')):
                credits_dict[soloist.get('instrument').get('title')] = []

            credits_dict[soloist.get('instrument').get('title')].append(credits_dict[soloist.get('person').get('name')])

        # add all the authors to credits
        for author in track_data.get('work').get('authors'):
            # check if the dict contains no list, create one
            credits_dict[author.get('authorType')] = [p.get('name') for p in author.get('persons')]

        # add the ensembles to credits
        credits_dict['Ensemble'] = []
        for ensemble in track_data.get('ensembles'):
            # check if the dict contains no list, create one
            credits_dict['Ensemble'].append(ensemble.get('name'))

        if len(credits_dict) > 0:
            # convert the dictionary back to a list of CreditsInfo
            return [CreditsInfo(sanitise_name(k), v) for k, v in credits_dict.items()]
        return None

    def get_track_download(self, track_id: str, quality_tier: int) -> TrackDownloadInfo:
        # get the encrypted_stream_url
        stream_data = self.session.get_track_stream(track_id, quality=quality_tier)

        if not stream_data:
            raise ValueError(f'Could not get stream data for track {track_id}')

        # file extension is only flac for FLAC and m4a for AAC
        file_ext = 'flac' if quality_tier == 90 else 'm4a'

        temp_location = f'{create_temp_filename()}.{file_ext}'

        # stream the downloaded encrypted file
        r = self.session.s.get(stream_data[0].get('url'), stream=True)
        total = int(r.headers['content-length'])

        # check if file is encrypted by checking the headers
        is_encrypted = False
        if r.headers.get('X-X'):
            # get the base key and the iv from the headers
            is_encrypted = True
            base_key, iv = r.headers['X-X'].split(' ')

            # get the actual key
            secret = 'mola*jbaf^*`*V^fG^lkf4fb_bba2'
            offset = 3
            # jesus christ?! just why? that's so dumb
            extended_key = ''.join(map(chr, [(ord(char) + offset + 65536) % 65536 for char in secret]))

            # now add the calculated extended key to the base key
            key = base_key + extended_key
            # calculate the SHA256 hash of the key
            key_checksum = SHA256.new(key.encode('utf-8')).hexdigest()[:16].encode('utf-8')
            iv = iv.encode('utf-8')

            # create a cipher object with an empty nonce, really important! Thanks @uhwot
            cipher = AES.new(key_checksum, AES.MODE_CTR, initial_value=iv, nonce=b'')

        try:
            with open(temp_location, 'wb') as f:
                try:
                    columns = os.get_terminal_size().columns
                    if os.name == 'nt':
                        bar = tqdm(total=total, unit='B', unit_scale=True, unit_divisor=1024, initial=0, miniters=1,
                                   ncols=(columns - self.oprinter.indent_number),
                                   bar_format=' ' * self.oprinter.indent_number + '{l_bar}{bar}{r_bar}')
                    else:
                        raise OSError
                except OSError:
                    bar = tqdm(total=total, unit='B', unit_scale=True, unit_divisor=1024, initial=0, miniters=1,
                               bar_format=' ' * self.oprinter.indent_number + '{l_bar}{bar}{r_bar}')

                if is_encrypted:
                    # decrypt while streaming the chunk
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(cipher.decrypt(chunk))
                            bar.update(len(chunk))
                else:
                    # just download the chunks
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
                            bar.update(len(chunk))

                bar.close()

        except KeyboardInterrupt:
            if os.path.isfile(temp_location):
                print(f'\tDeleting partially downloaded file "{str(temp_location)}"')
                silentremove(temp_location)
            raise KeyboardInterrupt

        # return the MP4 temp file, but tell orpheus to change the container to .m4a (AAC)
        return TrackDownloadInfo(
            download_type=DownloadEnum.TEMP_FILE_PATH,
            temp_file_path=temp_location
        )
