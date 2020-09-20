import logging
import os

from pythoncommons.file_utils import FileUtils
from pythoncommons.string_utils import StringUtils

PATCH_FILE_SEPARATOR = "."
REVIEW_BRANCH_SEP = "-"
FIRST_PATCH_NUMBER = "001"
LOG = logging.getLogger(__name__)


class PatchUtils:
    @staticmethod
    def extract_patch_number_from_filename_as_int(filename, pos=-2):
        # Assuming filename like: '/somedir/YARN-10277-test.0003.patch'
        return int(filename.split(PATCH_FILE_SEPARATOR)[pos])

    @staticmethod
    def extract_patch_number_from_filename_as_str(filename, pos=-2):
        # Assuming filename like: '/somedir/YARN-10277-test.0003.patch'
        return filename.split(PATCH_FILE_SEPARATOR)[pos]

    @staticmethod
    def get_next_patch_filename(filename, pos=-2):
        # Assuming filename like: '/somedir/YARN-10277-test.0003.patch'
        split = filename.split(PATCH_FILE_SEPARATOR)
        increased_str = StringUtils.increase_numerical_str(split[pos])
        split[pos] = increased_str
        return PATCH_FILE_SEPARATOR.join(split)

    @staticmethod
    def get_next_filename(patch_dir, list_of_prev_patches):
        list_of_prev_patches = sorted(list_of_prev_patches, reverse=True)
        LOG.info("Found patches: %s", list_of_prev_patches)
        if len(list_of_prev_patches) == 0:
            return FileUtils.join_path(patch_dir, FIRST_PATCH_NUMBER), FIRST_PATCH_NUMBER
        else:
            latest_patch = list_of_prev_patches[0]
            last_patch_num = PatchUtils.extract_patch_number_from_filename_as_str(latest_patch)
            next_patch_filename = PatchUtils.get_next_patch_filename(latest_patch)
            return (
                FileUtils.join_path(patch_dir, next_patch_filename),
                StringUtils.increase_numerical_str(last_patch_num),
            )

    @staticmethod
    def get_next_review_branch_name(branches, sep=REVIEW_BRANCH_SEP):
        # review-YARN-10277-3
        # review-YARN-10277-2
        # review-YARN-10277
        sorted_branches = sorted(branches, reverse=True)
        if len(sorted_branches) == 0:
            raise ValueError("Expected a list of branches with size 1 at least. List: %s", sorted_branches)

        latest_branch = sorted_branches[0]
        parts = latest_branch.split(sep)

        if len(parts) < 3:
            raise ValueError(
                "Expected at least 3 components (separated by '-') of branch name: {}, encountered: {}",
                latest_branch,
                len(parts),
            )

        # No branch postfix, e.g. review-YARN-10277
        if len(parts) == 3:
            return sep.join(parts) + sep + "2"
        elif len(parts) == 4:
            return sep.join(parts[0:3]) + sep + StringUtils.increase_numerical_str(parts[3])
        else:
            raise ValueError(
                "Unexpected number of components (separated by '-') of branch name: {}, "
                "encountered # of components: {}", latest_branch, len(parts))

    @staticmethod
    def save_diff_to_patch_file(diff, file):
        if not diff or diff == "":
            LOG.error("Diff was empty. Patch file is not created!")
            return False
        else:
            diff += os.linesep
            LOG.info("Saving diff to patch file: %s", file)
            LOG.debug("Diff: %s", diff)
            FileUtils.save_to_file(file, diff)
            return True