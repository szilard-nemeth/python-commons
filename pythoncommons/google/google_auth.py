import os
import pickle
import os.path
from typing import List

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from pythoncommons.google.common import ServiceType


class GoogleApiAuthorizer:
    CREDENTIALS_FILENAME = 'credentials.json'
    TOKEN_FILENAME = 'token.pickle'
    DEFAULT_SCOPES = ["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"]
    # If modifying these scopes, delete the file token.pickle.
    DEFAULT_WEBSERVER_PORT = 49555

    def __init__(self,
                 service_type: ServiceType,
                 scopes: List[str] = None,
                 server_port: int = DEFAULT_WEBSERVER_PORT,
                 token_filename: str = TOKEN_FILENAME,
                 credentials_filename: str = CREDENTIALS_FILENAME):
        self.service_type = service_type
        self._set_scopes(scopes)
        self.server_port = server_port
        self.token_filename = token_filename
        self.creds_filename = credentials_filename

    def _set_scopes(self, scopes):
        self.scopes = scopes
        if self.scopes is None:
            self.scopes = self.service_type.default_scopes

        # https://stackoverflow.com/a/51643134/1106893
        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
        self.scopes.extend(self.DEFAULT_SCOPES)

    def authorize(self):
        creds = self._load_token()
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            creds = self._handle_login(creds)
        return creds

    def _load_token(self):
        """
        The file token.pickle stores the user's access and refresh tokens, and is
        created automatically when the authorization flow completes for the first
        time.
        """
        creds = None
        if os.path.exists(self.token_filename):
            with open(self.token_filename, 'rb') as token:
                creds = pickle.load(token)
        return creds

    def _handle_login(self, creds):
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(self.creds_filename, self.scopes)
            self.authed_creds = flow.run_local_server(port=self.server_port)

            # TODO Save credentials tied to profile (email address)
            session = flow.authorized_session()
            profile_info = session.get('https://www.googleapis.com/userinfo/v2/me').json()
            print(profile_info)
        # Save the credentials for the next run
        self._write_token()
        return self.authed_creds

    def _write_token(self):
        with open(self.token_filename, 'wb') as token:
            pickle.dump(self.authed_creds, token)
