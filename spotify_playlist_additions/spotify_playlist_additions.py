"""Main module."""

import asyncio
import logging
from typing import Dict, List
from urllib import parse
from urllib.parse import urlparse

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse
from async_spotify.api.spotify_api_client import SpotifyApiClient
from async_spotify.authentification.authorization_flows import AuthorizationCodeFlow
from yarl import URL

from spotify_playlist_additions.playlists.autoadd import AutoAddPlaylist
from spotify_playlist_additions.playlists.autoremove import AutoRemovePlaylist
from spotify_playlist_additions.user import SpotifyUser
from spotify_playlist_additions.utils import get_scope

LOG = logging.getLogger(__name__)


class SpotifyOauthError(Exception):
    """ Error during Auth Code or Implicit Grant flow """
    def __init__(self,
                 message,
                 error=None,
                 error_description=None,
                 *args,
                 **kwargs):
        self.error = error
        self.error_description = error_description
        self.__dict__.update(kwargs)
        super(SpotifyOauthError, self).__init__(message, *args, **kwargs)


class SpotifyPlaylistEngine:
    """The main driver for Spotify Playlist Additions. Contains the main loop, functionality branches out from here.
    Contains logic for detection of a skipped or fully listened track and passes this information to various playlist
    additions that utilize it to perform actions on a playlist
    """
    def __init__(self, search_wait: float = 5000, playlist: dict = None):
        """Initializer for a SpotifyPlaylistEngine. Nothing that absolutely requires an internet connection should be
        located here.

        Args:
            search_wait: How long to wait before performing a track search. Essentially, the rate of checking or time
            per frame
            playlist: The playlist dictionary retrieved directly from the spotify API.
        """
        self._users: Dict[str, SpotifyUser] = {}
        app = self._create_http_server()
        self._runner = web.AppRunner(app)
        self._site = None

    async def start(self):
        await self._start_http_server()

    async def stop(self):
        await self._site.stop()
        await self._runner.shutdown()

        await asyncio.gather(user.stop() for user in self._users.values())

    async def _start_http_server(self):
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, port=8080)
        LOG.info("Listening on port 8080")
        await self._site.start()

    def _create_http_server(self):
        app = web.Application()
        app.add_routes([
            web.get("/callback", self.auth_callback),
            web.get("/spotifyadditions", self.redirect_callback)
        ])
        return app

    async def auth_callback(self, request: Request) -> StreamResponse:
        form = SpotifyPlaylistEngine.parse_auth_response_url(request.url)

        flow = AuthorizationCodeFlow()
        flow.load_from_env()
        flow.scopes = [">:("]
        client = SpotifyApiClient(flow, hold_authentication=True)

        await client.get_auth_token_with_code(form["code"])

        await client.create_new_client(request_limit=1500)
        name = await client.user.me()
        
        # Use an existing user if it already exists
        if user := self._users.get(name["id"], None):
            await user.choose_playlist_cli()
            return web.Response(text="Started another playlist for you!")

        # Create a new user if it isnt in the dictionary
        user = SpotifyUser(client, 2000)
        await user.start()
        
        self._users[name["id"]] = user

        return web.Response(text="Started your spotify playlist!")

    async def redirect_callback(self, request: Request) -> StreamResponse:
        addons = [AutoAddPlaylist, AutoRemovePlaylist]
        scope = get_scope(addons)
        flow = AuthorizationCodeFlow()
        flow.load_from_env()
        flow.scopes = scope
        client = SpotifyApiClient(flow)
        url = client.build_authorization_url()

        return web.HTTPFound(url)

    @staticmethod
    def parse_auth_response_url(url: URL):
        query_s = urlparse(str(url)).query
        form = dict(parse.parse_qsl(query_s))
        if "error" in form:
            raise SpotifyOauthError("Received error from auth server: "
                                    "{}".format(form["error"]),
                                    error=form["error"])
        return form
