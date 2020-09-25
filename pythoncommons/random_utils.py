import secrets
import string


class RandomUtils:
    @classmethod
    def get_secure_random_string(cls, length):
        secure_str = ''.join((secrets.choice(string.ascii_letters) for i in range(length)))
        return secure_str
