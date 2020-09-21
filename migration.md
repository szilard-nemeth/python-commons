

## Pip install commands
```
pip3.8 install -r requirements.txt -v --upgrade

pip3.8 install git+ssh://git@github.com/szilard-nemeth/python-commons.git --upgrade

pip3 install git+ssh://git@github.com/szilard-nemeth/python-commons.git --upgrade
```



## Check where the package is installed?
```
find /usr/local/lib/python3.8 | grep commons
find /Library/Frameworks/Python.framework/Versions/3.8/lib/python3.8/site-packages | grep commons
```

## Add this as a dependency to projects, into requirements.txt file
```
git+ssh://git@github.com/szilard-nemeth/python-commons.git
```


## Import statements
```

from pythoncommons.file_utils import FileUtils as CommonsFileUtils
from pythoncommons.file_utils import FileUtils
```


## commit messages

### Commit into this project
Source project: google-chrome-toolkit
```
git ci -m "Add date_utils and string_utils from google-chrome-toolkit"
```

### Commit into project that depend on python-commons
1. "Moved dependencies to python-commons: StringUtils, DateUtils"
2. "Moved dependencies to python-commons"
3. Complete command: git commit with message
```
git ci -m "Moved dependencies to python-commons


https://github.com/szilard-nemeth/python-commons"
```