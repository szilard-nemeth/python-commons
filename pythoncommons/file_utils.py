class FileUtils:
    @classmethod
    def write_to_file(cls, file_path, data):
        f = open(file_path, 'w')
        f.write(data)
        f.close()
