import logging
from typing import List

from googleapiclient.discovery import build

from pythoncommons.google.google_auth import GoogleApiAuthorizer
from pythoncommons.string_utils import StringUtils, auto_str

LOG = logging.getLogger(__name__)


class DriveApiMimeTypes:
    # https://stackoverflow.com/questions/4212861/what-is-a-correct-mime-type-for-docx-pptx-etc
    # https://stackoverflow.com/questions/11894772/google-drive-mime-types-listing
    MIME_MAPPINGS = {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "MS Presentation (pptx)",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "MS Word document (docx)",
        "application/vnd.ms-powerpoint": "MS Presentation (ppt)",

        "application/pdf": "PDF document",
        "application/x-apple-diskimage": "Apple disk image",
        "application/zip": "Zip file",
        "text/plain": "Plain text file",
        "application/msword": "MS Word document (doc)",
        
        "image/jpeg": "JPEG image",
        "image/gif": "GIF image",
        "video/mp4": "Video (mp4)",

        "application/vnd.google-apps.spreadsheet": "Google sheet",
        "application/vnd.google-apps.folder": "Google drive folder",
        "application/vnd.google-apps.document": "Google doc",
        "application/vnd.google-apps.form": "Google form",
        "application/vnd.google-apps.presentation": "Google presentation",
        "application/vnd.google-apps.map": "Google map",
    }


class FileField:
    F_OWNER = "owners"
    SHARING_USER = "sharingUser"
    SHARED_WITH_ME_TIME = "sharedWithMeTime"
    MODIFIED_TIME = "modifiedTime"
    CREATED_TIME = "createdTime"
    LINK = "webViewLink"
    MIMETYPE = "mimeType"
    NAME = "name"
    ID = "id"

    _ALL_FIELDS_WITH_DISPLAY_NAME = [(ID, "ID"),
                                     (NAME, "Name"),
                                     (MIMETYPE, "Type"),
                                     (LINK, "Link"),
                                     (CREATED_TIME, "Created date"),
                                     (MODIFIED_TIME, "Last modified time"),
                                     (SHARED_WITH_ME_TIME, "Shared with me date"),
                                     (F_OWNER, "Owner")]

    PRINTABLE_FIELD_DISPLAY_NAMES = ["Name", "Link", "Shared with me date", "Owner", "Type"]
    # FIELDS_TO_PRINT = [tup[0] for tup in FIELDS_TO_PRINT]

    BASIC_FIELDS_COMMA_SEPARATED = ", ".join([ID, NAME])
    GOOGLE_API_FIELDS = [tup[0] for tup in _ALL_FIELDS_WITH_DISPLAY_NAME]
    GOOGLE_API_FIELDS_COMMA_SEPARATED = ", ".join(GOOGLE_API_FIELDS)
    FIELD_DISPLAY_NAMES = [tup[1] for tup in _ALL_FIELDS_WITH_DISPLAY_NAME]


class GenericUserField:
    UNKNOWN_USER = 'unknown'
    EMAIL_ADDRESS = 'emailAddress'
    DISPLAY_NAME = 'displayName'


class GenericApiField:
    PAGING_NEXT_PAGE_TOKEN = "nextPageToken"


@auto_str
class DriveApiUser(dict):
    def __init__(self, owner_dict):
        super(DriveApiUser, self).__init__()
        # convenience variables
        email_field = GenericUserField.EMAIL_ADDRESS
        display_name_field = GenericUserField.DISPLAY_NAME
        unknown_user = GenericUserField.UNKNOWN_USER

        email = owner_dict[email_field] if email_field in owner_dict else unknown_user
        name = owner_dict[display_name_field] if display_name_field in owner_dict else unknown_user
        self.email = email
        self.name = StringUtils.replace_special_chars(name)

    def __repr__(self):
        return self.__str__()


@auto_str
class DriveApiFile(dict):
    def __init__(self, id, name, link, created_date, modified_date, shared_with_me_date, mime_type, owners,
                 sharing_user: DriveApiUser):
        super(DriveApiFile, self).__init__()
        self.id = id
        self.name = StringUtils.replace_special_chars(name)
        self.link = link
        self.created_date = created_date
        self.modified_date = modified_date
        self.shared_with_me_date = shared_with_me_date
        self.mime_type = mime_type
        self.owners = owners

        sharing_user.name = StringUtils.replace_special_chars(sharing_user.name)
        self.sharing_user = sharing_user

    def __repr__(self):
        return self.__str__()


class DriveApiWrapper:
    DEFAULT_API_VERSION = 'v3'
    DEFAULT_ORDER_BY = "sharedWithMeTime desc"
    QUERY_SHARED_WITH_ME = "sharedWithMe"
    DEFAULT_PAGE_SIZE = 100

    def __init__(self, authorizer: GoogleApiAuthorizer, api_version: str = None):
        self.creds = authorizer.authorize()
        if not api_version:
            api_version = authorizer.service_type.default_api_version
        self.service = build(authorizer.service_type.service_name, api_version, credentials=self.creds)
        self.files_service = self.service.files()

    def print_shared_files(self, page_size=DEFAULT_PAGE_SIZE, fields=None, order_by=DEFAULT_ORDER_BY):
        files = self.get_shared_files(page_size=page_size, fields=fields, order_by=order_by)
        for file in files:
            LOG.info(u'{0} ({1})'.format(file[FileField.NAME], file[FileField.ID]))

    def get_shared_files(self, page_size=DEFAULT_PAGE_SIZE, fields: List[str] = None, order_by: str = DEFAULT_ORDER_BY):
        if not fields:
            fields = FileField.BASIC_FIELDS_COMMA_SEPARATED
        fields_str = self.get_field_names_with_pagination(fields)
        return self.list_files_with_paging(self.QUERY_SHARED_WITH_ME, page_size, fields_str, order_by)

    @staticmethod
    def get_field_names_with_pagination(fields, resource_type='files'):
        # File fields are documented here: https://developers.google.com/drive/api/v3/reference/files#resource
        fields_str = "{res}({fields})".format(res=resource_type, fields=fields)
        return "{}, {}".format(GenericApiField.PAGING_NEXT_PAGE_TOKEN, fields_str)

    def list_files_with_paging(self, query, page_size, fields, order_by):
        result_files = []
        request = self.files_service.list(q=query, pageSize=page_size, fields=fields, orderBy=order_by)
        while request is not None:
            files_doc = request.execute()
            if files_doc:
                api_file_results = files_doc.get('files', [])
                drive_api_files = [DriveApiWrapper._convert_to_drive_file_object(i) for i in api_file_results]
                result_files.extend(drive_api_files)
            else:
                LOG.warning('No files found.')
            request = self.files_service.list_next(request, files_doc)

        return result_files

    @classmethod
    def convert_mime_type(cls, mime_type):
        if mime_type in DriveApiMimeTypes.MIME_MAPPINGS:
            return DriveApiMimeTypes.MIME_MAPPINGS[mime_type]
        else:
            LOG.warning("MIME type not found among possible values: %s. Using MIME type value as is", mime_type)
            return mime_type

    @classmethod
    def _convert_to_drive_file_object(cls, item) -> DriveApiFile:
        list_of_owners_dicts = item['owners']
        owners = [DriveApiUser(owner_dict) for owner_dict in list_of_owners_dicts]

        unknown_user = {GenericUserField.EMAIL_ADDRESS: GenericUserField.UNKNOWN_USER,
                        GenericUserField.DISPLAY_NAME: GenericUserField.UNKNOWN_USER}
        sharing_user_dict = item[FileField.SHARING_USER] if FileField.SHARING_USER in item else unknown_user
        sharing_user = DriveApiUser(sharing_user_dict)

        return DriveApiFile(item[FileField.ID],
                            item[FileField.NAME],
                            item[FileField.LINK],
                            item[FileField.CREATED_TIME],
                            item[FileField.MODIFIED_TIME],
                            item[FileField.SHARED_WITH_ME_TIME],
                            item[FileField.MIMETYPE], owners, sharing_user)