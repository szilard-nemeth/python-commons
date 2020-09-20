import logging

LOG = logging.getLogger(__name__)


class ObjUtils:
    @staticmethod
    def print_properties(obj):
        LOG.info("Printing properties of obj: %s", obj)
        for prop, value in vars(obj).items():
            LOG.info("%s: %s", prop, value)
