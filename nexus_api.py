import http.client
import json
from typing import TypedDict

from .util import logger


class NexusFileDetails(TypedDict):
    id: list[int]
    uid: int
    file_id: int
    name: str
    version: str
    category_id: int
    category_name: str
    is_primary: bool
    size: int
    file_name: str
    uploaded_timestamp: int
    uploaded_time: str
    mod_version: str
    external_virus_scan_url: str
    description: str
    size_kb: int
    size_in_bytes: int
    changelog_html: str
    content_preview_link: str
    md5: str


class NexusUserResponse(TypedDict):
    member_id: int
    member_group_id: int
    name: str


class NexusModResponse(TypedDict):
    name: str
    summary: str
    description: str
    picture_url: str
    mod_downloads: int
    mod_unique_downloads: int
    uid: int
    user: NexusUserResponse
    mod_id: int
    game_id: int
    allow_rating: bool
    domain_name: str
    category_id: int
    version: str
    endorsement_count: int
    created_timestamp: int
    created_time: str
    updated_timestamp: int
    updated_time: str
    author: str
    uploaded_by: str
    uploaded_users_profile_url: str
    contains_adult_content: bool
    status: str
    available: bool


class NexusMD5Response(TypedDict):
    mod: NexusModResponse
    file_details: NexusFileDetails


class NexusApi:

    _BASE_URL = "api.nexusmods.com"
    _API_KEY_HEADER = "apiKey"

    _PATHS = {
        "VALIDATE": "/v1/users/validate.json",
        "MD5": "/v1/games/{game_domain_name}/mods/md5_search/{md5_hash}.json",
    }

    __api_key: str = None

    def __init__(self, api_key):
        self.__api_key = api_key

    def validate_api_key(self) -> bool:
        try:
            self._make_nexus_request(self._BASE_URL, self._PATHS["VALIDATE"])
            return True
        except Exception:
            return False

    def md5_lookup(self, md5_hash: str) -> list[NexusMD5Response] | None:
        path_vars = {"md5_hash": md5_hash, "game_domain_name": "skyrimspecialedition"}
        try:
            response = self._make_nexus_request(
                self._BASE_URL, self._PATHS["MD5"], path_vars
            )
            return response
        except Exception as e:
            logger.error(e)
            return None

    def _make_nexus_request(self, base_url: str, endpoint: str, path_vars=None):
        return self._make_get_request(base_url, endpoint, path_vars)

    def _make_get_request(self, base_url: str, endpoint_template: str, path_vars=None):
        conn = None
        try:
            conn = http.client.HTTPSConnection(base_url)
            headers = {self._API_KEY_HEADER: self.__api_key}

            if path_vars:
                endpoint = endpoint_template.format(**path_vars)
            else:
                endpoint = endpoint_template

            conn.request("GET", endpoint, headers=headers)
            response = conn.getresponse()

            if response.status != 200:
                raise Exception(
                    f"Request failed with status: {response.status} {response.reason}"
                )

            data = response.read().decode("utf-8")
            return json.loads(data)  # Parse the JSON response
        except Exception as e:
            print(f"An error occurred: {e}")
            return None
        finally:
            if conn:
                conn.close()
