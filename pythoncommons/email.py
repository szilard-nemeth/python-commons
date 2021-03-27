import logging
import zipfile
from email.mime.text import MIMEText
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from typing import List

from pythoncommons.file_utils import FileUtils

LOG = logging.getLogger(__name__)


class EmailAccount:
    def __init__(self, user: str, password: str):
        self.user: str = user
        self.password: str = password


class EmailConfig:
    def __init__(self, smtp_server: str, smtp_port: int, email_account: EmailAccount):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email_account = email_account


class EmailService:
    def __init__(self, email_config: EmailConfig):
        self.conf = email_config

    def send_mail(self, sender: str, subject: str, body: str, recipients: List[str], attachment_file=None):
        self._validate_config(recipients)

        email_msg = None
        if attachment_file:
            FileUtils.ensure_file_exists(attachment_file)
            # https://stackoverflow.com/a/169406/1106893
            email_msg = MIMEMultipart()
            email_msg.attach(MIMEText(str(body), "plain"))
            attachment = self._create_attachment(attachment_file)
            email_msg.attach(attachment)
        else:
            email_msg = MIMEText(str(body))

        recipients_comma_separated = ', '.join(recipients)
        email_msg = MIMEText(str(body))
        email_msg['From'] = sender
        email_msg['To'] = recipients_comma_separated
        email_msg['Subject'] = subject
        email_msg.preamble = 'I am not using a MIME-aware mail reader.\n'

        self._connect_to_server_and_send(email_msg, recipients, recipients_comma_separated, sender)

    def _validate_config(self, recipients):
        if not recipients:
            LOG.error('Cannot send email as recipient email addresses are not set!')
            return
        if not self.conf:
            raise ValueError("Email config is not set!")
        if not all(attr is not None for attr in vars(self.conf)):
            raise ValueError(f"Some attribute of EmailConfig is not set. Config object: {self.conf}")
        if not self.conf.email_account.user:
            raise ValueError(f"Wrong email server config. Username must be set!")
        if not self.conf.email_account.password:
            raise ValueError(f"Wrong email server config. Password must be set!")

    def _connect_to_server_and_send(self, email_msg, recipients, recipients_comma_separated, sender):
        server = smtplib.SMTP_SSL(self.conf.smtp_server, self.conf.smtp_port)
        LOG.info('Sending mail to recipients: %s', recipients_comma_separated)
        server.ehlo()
        server.login(self.conf.email_account.user, self.conf.email_account.password)
        server.sendmail(sender, recipients, email_msg.as_string())
        server.quit()

    @staticmethod
    def _create_attachment(file_path):
        msg = MIMEBase('application', 'zip')
        file = open(file_path, "rb")
        msg.set_payload(file.read())
        encoders.encode_base64(msg)
        msg.add_header('Content-Disposition', 'attachment',
                       filename=FileUtils.basename(file_path) + '.zip')
        return msg
