import json
import logging
import random
import urllib
import urllib.request as request
import urllib.error as url_error
from typing import Dict, Set, Callable

LOG = logging.getLogger(__name__)


class NetworkUtils:
    @staticmethod
    def is_port_in_use(port):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0

    @staticmethod
    def get_random_port():
        return random.randrange(5000, 6000)

    @staticmethod
    def wait_for_internet_connection():
        counter = 0
        while True:
            try:
                # ping google
                if counter > 0:
                    LOG.info('Waiting for internet connection, try count: %s', counter)
                response = request.urlopen('http://google.com', timeout=1)
                return
            except url_error.URLError:
                pass

    @staticmethod
    def fetch_json(url, strict=False,
                   do_not_raise_http_statuses: Set[int] = None,
                   http_callbacks: Dict[int, Callable] = None):
        """ Load data from specified url """
        try:
            LOG.debug("Making request to URL: %s", url)
            ourl = urllib.request.urlopen(url)
            codec = ourl.info().get_param("charset")
            content = ourl.read().decode(codec)
        except urllib.error.HTTPError as e:
            if do_not_raise_http_statuses and e.code in do_not_raise_http_statuses:
                if http_callbacks and e.code in http_callbacks:
                    http_callbacks[e.code]()
                return {}
            else:
                raise e
        return json.loads(content, strict=strict)
