"""
Music Stream Migration WIP

Export music streaming information from a users profile.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import tomllib

import spotipy


def _load_configuration(path):
    with open(path, "rb") as config:
        return tomllib.load(config)


def _parse_inputs():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "-c",
        "--configs",
        default="config.toml",
        type=_load_configuration,
        help="User streaming configuration file.",
    )
    parser.add_argument(
        "--user-data",
        default="user_data.json",
        type=Path,
        help="Output user data.",
    )

    return parser.parse_args()


def _access_spotify_user_data(user_data: dict, scope: str, redirect_uri: str):
    return spotipy.Spotify(
        auth_manager=spotipy.oauth2.SpotifyOAuth(
            client_id=user_data["client_id"],
            client_secret=user_data["client_secret"],
            redirect_uri=redirect_uri,
            scope=scope,
            cache_path=".spotifycache",
        )
    )


def _retrieve_data(data: spotipy.Spotify, dataset, owner=None):
    retrieved = []
    while dataset:
        if owner:
            for item in dataset["items"]:
                if item["owner"]["id"] == owner:
                    retrieved.append(item)

        else:
            retrieved.extend(dataset["items"])

        dataset = data.next(dataset) if dataset["next"] else None

    return retrieved


def fetch_user_saved_playlists(data: spotipy.Spotify, owner):
    """Retrieve all playlists saved by the user."""
    return [
        {
            "playlist_id": playlist["id"],
            "name": playlist["name"],
            "description": playlist["description"],
            "is_public": playlist["public"],
            "total_tracks": playlist["tracks"]["total"],
            "tracks": [
                _structure_spotify_track_data(entry)
                for entry in _retrieve_data(
                    data,
                    data.playlist_items(
                        playlist_id=playlist["id"],
                        additional_types=playlist["tracks"],
                    ),
                )
            ],
        }
        for playlist in _retrieve_data(data, data.current_user_playlists(), owner)
    ]


def fetch_user_saved_tracks(data: spotipy.Spotify):
    """Retrieve all tracks saved by the user."""
    return _retrieve_data(data, data.current_user_saved_tracks())


def _top_level_structure(source, user_id, user_uri):
    return {
        "source": source,
        "exported_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user_id": user_id,
        "user_uri": user_uri,
        "playlists": [],
        "liked_tracks": [],
    }


def _structure_spotify_track_data(track):
    return {
        "track_id": track["track"]["id"],
        "isrc": track["track"]["external_ids"].get("isrc"),
        "name": track["track"]["name"],
        "artists": [artist["name"] for artist in track["track"]["artists"]],
        "album": track["track"]["album"]["name"],
        "duration_ms": track["track"]["duration_ms"],
        "explicit": track["track"]["explicit"],
        "disc_number": track["track"]["disc_number"],
        "track_number": track["track"]["track_number"],
        "uri": track["track"]["uri"],
        "added_at": track["added_at"],
    }


def _extract_spotify_data(configs):
    data = _access_spotify_user_data(
        user_data=configs,
        scope="playlist-read-private user-library-read user-top-read user-read-private",
        redirect_uri=configs["redirect_uri"],
    )

    user_data = _top_level_structure("spotify", data.me()["id"], data.me()["uri"])
    user_data["playlists"] = fetch_user_saved_playlists(data, owner=configs["username"])
    user_data["liked_tracks"] = [
        _structure_spotify_track_data(entry) for entry in fetch_user_saved_tracks(data)
    ]

    return user_data


def _main():
    args = _parse_inputs()
    user_data = _extract_spotify_data(args.configs["spotify"])

    if args.user_data:
        with open(args.user_data, "w", encoding="utf-8") as data_file:
            json.dump(user_data, data_file, ensure_ascii=True)

    # tidal_session = tidalapi.Session()
    # tidal_session.login_oauth_simple()


if __name__ == "__main__":
    _main()
