from enum import Enum


class ServiceType(Enum):
    DRIVE = ('drive', ['https://www.googleapis.com/auth/drive.metadata.readonly'], "v3")
    GMAIL = ('gmail', ['https://www.googleapis.com/auth/gmail.readonly'], "v1")

    def __init__(self, name, scopes, api_version):
        self.service_name = name
        self.default_scopes = scopes
        self.default_api_version = api_version
