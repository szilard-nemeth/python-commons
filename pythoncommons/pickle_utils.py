import pickle


class PickleUtils:
    @staticmethod
    def dump(data, file):
        with open(file, "wb") as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(file):
        with open(file, "rb") as f:
            # The protocol version used is detected automatically, so we do not
            # have to specify it.
            return pickle.load(f)
