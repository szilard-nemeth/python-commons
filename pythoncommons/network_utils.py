import logging
import random
import urllib.request as request
import urllib.error as url_error
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
