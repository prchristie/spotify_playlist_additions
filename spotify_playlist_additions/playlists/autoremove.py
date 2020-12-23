"""
Contains a child class of an AbstractPlaylist that implements functionality for automatically removing songs that
were detected to be skipped
"""

import logging
from typing import Any

from async_spotify.api.spotify_api_client import SpotifyApiClient
from spotify_playlist_additions.playlists.abstract import AbstractPlaylist

LOG = logging.getLogger(__name__)


class AutoRemovePlaylist(AbstractPlaylist):
    """A playlist addon that removes songs that were detected to be skipped.
    """

    scope = "user-read-currently-playing playlist-modify-public"

    async def start(self) -> Any:
        """Method called at the start of runtime. Only called once.
        """
        pass

    async def stop(self) -> Any:
        """Method called at the end of runtime. Only called once
        """
        pass

    async def handle_skipped_track(self, track: dict,
                                   spotify_client: SpotifyApiClient) -> Any:
        """
        Removes the track from the given playlist

        Args:
            track: The skipped track retrieved from the Spotify API.
                Retains the exact format that Spotify defines in their API.
        """

        LOG.info("Removing %s from playlist", track["item"]["name"])
        spotify_client.playlists.remove_tracks(
            self._playlist["id"], {"tracks": [track["item"]["id"]]})

    async def handle_fully_listened_track(
            self, track: dict, spotify_client: SpotifyApiClient) -> Any:
        """Called on each configured playlist when the main loop detects a
        fully listened track (to within a degree of uncertainty)

        Args:
            track: The fully listened track retrieved from the Spotify API.
                Retains the exact format that Spotify defines in their API
        """

        pass
