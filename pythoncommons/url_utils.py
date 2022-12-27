import logging
import re
from urllib.parse import urlparse
import requests

LOG = logging.getLogger(__name__)


class UrlUtils:
    @staticmethod
    def extract_from_str(s):
        return re.search("(?P<url>https?://[^\s]+)", s).group("url")

    @staticmethod
    def get_hostname_from_url(url):
        # from urlparse import urlparse  # Python 2
        parsed_uri = urlparse(url)
        return "{uri.scheme}://{uri.netloc}/".format(uri=parsed_uri)

    @staticmethod
    def get_url_components(url):
        # from urlparse import urlparse  # Python 2
        parsed_uri = urlparse(url)
        # hostname = {str} 'szyszy.ddns.net'
        # netloc = {str} 'szyszy.ddns.net:33000'
        # params = {str} ''
        # password = {NoneType} None
        # path = {str} '/'
        # port = {int} 33000
        # query = {str} ''
        # scheme = {str} 'http'
        # username = {NoneType} None
        return {
            "hostname": parsed_uri.hostname,
            "netloc": parsed_uri.netloc,
            "scheme": parsed_uri.scheme,
        }

    @staticmethod
    def url_ok(url, silent=False):
        print_exc_info = not silent
        try:
            r = requests.head(url)
        except requests.exceptions.RequestException as e:

            LOG.exception("Failed to connect to URL: {}".format(url), exc_info=print_exc_info)
            return False
        return r.status_code == 200
