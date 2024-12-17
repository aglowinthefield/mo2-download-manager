import http.client
import json

from .util import logger

class NexusApi:

    BASE_URL = "api.nexusmods.com"
    API_KEY_HEADER = "apiKey"

    PATHS = {
        "VALIDATE": "/v1/users/validate.json",
        "MD5": "/v1/games/{game_domain_name}/mods/md5_search/{md5_hash}.json"
    }

    __api_key: str = None

    def __init__(self, api_key):
        self.__api_key = api_key

    def validate_api_key(self) -> bool:
        try:
            self._make_nexus_request(self.BASE_URL, self.PATHS["VALIDATE"])
            return True
        except Exception:
            return False

    def md5_lookup(self, md5_hash: str):
        path_vars = { "md5_hash": md5_hash, "game_domain_name": "skyrimspecialedition" }
        try:
            response = self._make_nexus_request(self.BASE_URL, self.PATHS["MD5"], path_vars)
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
            headers = { self.API_KEY_HEADER: self.__api_key }

            if path_vars:
                endpoint = endpoint_template.format(**path_vars)
            else:
                endpoint = endpoint_template

            conn.request("GET", endpoint, headers=headers)
            response = conn.getresponse()

            if response.status != 200:
                raise Exception(f"Request failed with status: {response.status} {response.reason}")

            data = response.read().decode("utf-8")
            return json.loads(data)  # Parse the JSON response
        except Exception as e:
            print(f"An error occurred: {e}")
            return None
        finally:
            if conn:
                conn.close()
