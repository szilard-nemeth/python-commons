import logging
import gspread
from gspread import SpreadsheetNotFound, WorksheetNotFound
from oauth2client.service_account import ServiceAccountCredentials

LOG = logging.getLogger(__name__)

SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
class GSheetOptions:
    def __init__(self, client_secret, spreadsheet, worksheet):
        self.client_secret = client_secret
        self.spreadsheet = spreadsheet
        self.worksheet = worksheet

    def __repr__(self):
        return repr((self.client_secret, self.spreadsheet, self.worksheet))

    def __str__(self):
        return self.__class__.__name__ + \
               " { " \
               "spreadsheet: " + self.spreadsheet + \
               ", worksheet: " + str(self.worksheet) + " }"


class GSheetWrapper:
    A1 = "A1"
    DEFAULT_RANGE_TO_CLEAR = 'A1:Z1000'

    def __init__(self, options):
        if not isinstance(options, GSheetOptions):
            raise ValueError('options must be an instance of GSheetOptions!')

        LOG.debug("GSheetWrapper options: %s", str(options))
        self.options = options

        if not options.client_secret:
            raise ValueError("Client secret should be specified!")

        self.creds = ServiceAccountCredentials.from_json_keyfile_name(options.client_secret, SCOPE)
        self.client = gspread.authorize(self.creds)

    def write_data(self, header, data, clear_range=True):
        # TODO add new column: Last updated date
        try:
            sheet = self.client.open(self.options.spreadsheet)
            worksheet = sheet.worksheet(self.options.worksheet)
        except SpreadsheetNotFound:
            raise ValueError("Spreadsheet was not found with name '{}'".format(self.options.spreadsheet))
        except WorksheetNotFound:
            raise ValueError("Worksheet was not found with name '{}'".format(self.options.worksheet))

        all_values = [header]
        all_values.extend(data)

        sheet_title = sheet.title
        worksheet_title = worksheet.title
        if clear_range:
            self.clear_range(sheet, sheet_title, worksheet_title)

        col_letter = chr(ord('a') + len(header) - 1).upper()
        rows = len(all_values)
        range_to_update = "{}:{}{}".format(self.A1, col_letter, rows)
        LOG.info("Adding values to sheet '%s', worksheet: '%s', range: '%s'", sheet_title, worksheet_title, range_to_update)
        sheet.values_update(
            '{}!{}'.format(self.options.worksheet, range_to_update),
            params={'valueInputOption': 'RAW'},
            body={'values': all_values}
        )

    def clear_range(self, sheet, sheet_title, worksheet_title):
        range_to_clear = self.DEFAULT_RANGE_TO_CLEAR
        LOG.info("Clearing all values from sheet '%s', worksheet: '%s', range: '%s'", sheet_title, worksheet_title,
                 range_to_clear)
        sheet.values_clear(range_to_clear)

        # It seems somehow gspread "memorizes" the cleared range and will add the new rows after the range, regardless
        # of what range have been provided with the range parameter to 'values_update'
        # HACK: Clear range A1:A1
        sheet.values_clear("A1:A1")
