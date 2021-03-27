import os
import pickle
import os.path
from typing import List

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


class GoogleApiAuthorizer:
    CREDENTIALS_FILENAME = 'credentials.json'
    TOKEN_FILENAME = 'token.pickle'
    # If modifying these scopes, delete the file token.pickle.
    DEFAULT_SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
    DEFAULT_WEBSERVER_PORT = 49555

    def __init__(self,
                 scopes: List[str] = None,
                 server_port: int = DEFAULT_WEBSERVER_PORT,
                 token_filename: str = TOKEN_FILENAME,
                 credentials_filename: str = CREDENTIALS_FILENAME):
        if scopes is None:
            self.scopes = GoogleApiAuthorizer.DEFAULT_SCOPES
        self.server_port = server_port
        self.token_filename = token_filename
        self.creds_filename = credentials_filename

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
        # Save the credentials for the next run
        self._write_token()
        return self.authed_creds

    def _write_token(self):
        with open(self.token_filename, 'wb') as token:
            pickle.dump(self.authed_creds, token)
