import logging
from email.mime.text import MIMEText
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from enum import Enum
from typing import List

from pythoncommons.file_utils import FileUtils

LOG = logging.getLogger(__name__)


class EmailMimeType(Enum):
    HTML = "html"
    PLAIN = "plain"


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
    def __init__(self, email_config: EmailConfig, batch_mode: bool = False):
        self.conf = email_config
        self.batch_mode = batch_mode
        self.logged_in = False
        self.conn = None

    def send_mail(
        self,
        sender: str,
        subject: str,
        body: str,
        recipients: List[str],
        attachment_file=None,
        override_attachment_filename: str = None,
        body_mimetype: EmailMimeType = EmailMimeType.PLAIN,
        with_retries: bool = True,
        retry_count: int = 3,
        log_exception_when_retried: bool = True,
    ):
        self._validate_config(recipients)
        saved_args = locals().copy()
        # Do not log HTML contents
        del saved_args["body"]
        LOG.debug("Received args: %s", saved_args)
        mime_text = MIMEText(str(body), body_mimetype.value)
        if not attachment_file:
            email_msg = mime_text
        else:
            FileUtils.ensure_file_exists(attachment_file)
            # https://stackoverflow.com/a/169406/1106893
            email_msg = MIMEMultipart()
            email_msg.attach(mime_text)
            if override_attachment_filename:
                attachment = self._create_attachment(attachment_file, attachment_name=override_attachment_filename)
            else:
                attachment = self._create_attachment(attachment_file)
            email_msg.attach(attachment)
        recipients_comma_separated = self._add_common_email_data(email_msg, recipients, sender, subject)
        self._connect_to_server_and_send(
            email_msg,
            recipients,
            recipients_comma_separated,
            sender,
            with_retries=with_retries,
            retry_count=retry_count,
            log_exception_when_retried=log_exception_when_retried,
        )

    @staticmethod
    def _add_common_email_data(email_msg, recipients, sender, subject):
        recipients_comma_separated = ", ".join(recipients)
        email_msg["From"] = sender
        email_msg["To"] = recipients_comma_separated
        email_msg["Subject"] = subject
        email_msg.preamble = "I am not using a MIME-aware mail reader.\n"
        return recipients_comma_separated

    def _validate_config(self, recipients):
        if not recipients:
            LOG.error("Cannot send email as recipient email addresses are not set!")
            return
        if not self.conf:
            raise ValueError("Email config is not set!")
        if not all(attr is not None for attr in vars(self.conf)):
            raise ValueError(f"Some attribute of EmailConfig is not set. Config object: {self.conf}")
        if not self.conf.email_account.user:
            raise ValueError("Wrong email server config. Username must be set!")
        if not self.conf.email_account.password:
            raise ValueError("Wrong email server config. Password must be set!")

    def _connect_to_server_and_send(
        self,
        email_msg,
        recipients,
        recipients_comma_separated,
        sender,
        with_retries: bool = True,
        retry_count: int = 3,
        log_exception_when_retried: bool = True,
    ):
        if not self.is_connected():
            self.conn = smtplib.SMTP_SSL(self.conf.smtp_server, self.conf.smtp_port)
            self.logged_in = False

        if with_retries:
            attempts_count: int = retry_count + 1
        else:
            attempts_count: int = 1

        for i in range(attempts_count):
            attempt = i + 1
            LOG.info(
                "[Attempt: %d / %d] Sending mail to recipients: %s with subject '%s'",
                attempt,
                attempts_count,
                recipients_comma_separated,
                email_msg["Subject"],
            )
            try:
                if not self.logged_in or not self.batch_mode:
                    self.conn.ehlo()
                    LOG.debug("SMPTP login")
                    self.conn.login(self.conf.email_account.user, self.conf.email_account.password)
                    self.logged_in = True

                self.conn.sendmail(sender, recipients, email_msg.as_string())

                if not self.batch_mode:
                    self.conn.quit()
                return
            except smtplib.SMTPServerDisconnected as e:
                # Try to reconnect
                self._reconnect()
                if attempt == attempts_count:
                    # Raise if we reached max retries or we just tried once without retries and it failed
                    raise e
                elif log_exception_when_retried:
                    LOG.exception("Failed to send email.", exc_info=True)

    def _reconnect(self):
        code, msg = self.conn.connect(self.conf.smtp_server, self.conf.smtp_port)
        LOG.info("Code: %s, msg: %s", code, msg)

    def is_connected(self):
        if not self.conn:
            return False
        try:
            status = self.conn.noop()[0]
        except smtplib.SMTPServerDisconnected:
            status = -1
        return True if status == 250 else False

    @staticmethod
    def _create_attachment(file_path: str, attachment_name: str = None):
        msg = MIMEBase("application", "zip")
        file = open(file_path, "rb")
        msg.set_payload(file.read())
        encoders.encode_base64(msg)

        attachment_fname_header = EmailService._get_attachment_name(attachment_name, file_path)
        msg.add_header("Content-Disposition", "attachment", filename=attachment_fname_header)
        return msg

    @staticmethod
    def _get_attachment_name(attachment_name, file_path):
        name = FileUtils.basename(file_path)
        if attachment_name:
            name: str = attachment_name
        if not name.endswith(".zip"):
            name += ".zip"
        return name
