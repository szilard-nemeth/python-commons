import os
import pickle
import os.path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


class GoogleApiAuthorizer:
    CREDENTIALS_FILENAME = 'credentials.json'
    TOKEN_FILENAME = 'token.pickle'
    # If modifying these scopes, delete the file token.pickle.
    SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
    SERVER_PORT = 49555

    def __init__(self):
        pass

    def authorize(self):
        creds = self._load_token()
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            creds = self._handle_login(creds)
        return creds

    @classmethod
    def _load_token(cls):
        """
        The file token.pickle stores the user's access and refresh tokens, and is
        created automatically when the authorization flow completes for the first
        time.
        """
        creds = None
        if os.path.exists(cls.TOKEN_FILENAME):
            with open(cls.TOKEN_FILENAME, 'rb') as token:
                creds = pickle.load(token)
        return creds

    @classmethod
    def _handle_login(cls, creds):
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                cls.CREDENTIALS_FILENAME, cls.SCOPES)
            creds = flow.run_local_server(port=cls.SERVER_PORT)
        # Save the credentials for the next run
        cls._write_token(creds)
        return creds

    @classmethod
    def _write_token(cls, creds):
        with open(cls.TOKEN_FILENAME, 'wb') as token:
            pickle.dump(creds, token)