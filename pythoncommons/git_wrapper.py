import logging
import os
from enum import Enum
from typing import List

from git import Repo, RemoteProgress, GitCommandError, Commit, Actor
from pythoncommons.git_constants import ORIGIN
from pythoncommons.git_constants import HEAD, COMMIT_FIELD_SEPARATOR
from pythoncommons.git_utils import GitUtils
from pythoncommons.jira_wrapper import PatchOverallStatus, AdvancedJiraPatch, PatchApply, JiraPatchStatus

FORMAT_CODE_HASH = "%H"
FORMAT_CODE_COMMIT_MSG = "%s"
FORMAT_CODE_DATE_ISO_8601 = "%cI"
FORMAT_CODE_AUTHOR = "%ae"
FORMAT_CODE_COMMITTER = "%ce"
DEFAULT_BRANCH = "master"

LOG = logging.getLogger(__name__)


# TODO GitLogLineFormat could store the actual log format strings
class GitLogLineFormat(Enum):
    ONELINE_WITH_DATE = 0
    ONELINE_WITH_DATE_AND_AUTHOR = 1
    ONELINE_WITH_DATE_AUTHOR_COMMITTER = 2


class GitWrapper:
    def __init__(self, base_path):
        self.repo_path = base_path
        self.repo = Repo(self.repo_path)

    # TODO Similar functionality here: yarndevtools.yarn_dev_tools.Setup._setup_gitpython_log
    @property
    def is_enabled_git_cmd_logging(self):
        return self.repo.git.GIT_PYTHON_TRACE is not False

    def enable_debug_logging(self, full=False):
        value = "full" if full else "1"
        os.environ["GIT_PYTHON_TRACE"] = value
        # https://github.com/gitpython-developers/GitPython/issues/222#issuecomment-68597780
        type(self.repo.git).GIT_PYTHON_TRACE = value

    def get_current_branch_name(self):
        return self.repo.git.rev_parse("HEAD", symbolic_full_name=True, abbrev_ref=True)

    def checkout_branch(self, branch, track=False):
        prev_branch = self.get_current_branch_name()
        LOG.info("Checking out branch: %s (Previous branch was: %s)", branch, prev_branch)
        if branch not in self.repo.heads:
            raise ValueError(f"Cannot find branch: {branch}")

        self.repo.git.checkout(branch)
        if track:
            LOG.info("Tracking branch '%s' with remote '%s'", branch, ORIGIN)
            self.repo.git.branch("-u", ORIGIN + "/" + branch)

    def move_branch(self, branch, move_to="HEAD"):
        if move_to == "HEAD":
            self.repo.git.branch("-f", branch)
        else:
            self.repo.git.branch("-f", branch, move_to)

    def checkout_new_branch(self, new_branch, base_ref):
        base_exist = self.is_branch_exist(base_ref)
        if not base_exist:
            return False

        prev_branch = self.get_current_branch_name()
        LOG.info(
            "Checking out new branch: %s based on ref: %s (Previous branch was: %s)", new_branch, base_ref, prev_branch
        )
        try:
            self.repo.git.checkout(base_ref, b=new_branch)
        except GitCommandError:
            LOG.exception("Git checkout failed!", exc_info=True)
            return False
        return True

    def pull(self, remote_name, ff_only=False):
        progress = ProgressPrinter("pull")
        remote = self.repo.remote(name=remote_name)
        LOG.info("Pulling remote: %s", remote_name)

        kwargs = {}
        if ff_only:
            kwargs["ff-only"] = True
        try:
            result = remote.pull(progress=progress, **kwargs)
            LOG.debug("Result of git pull: %s", result)
        except GitCommandError:
            LOG.exception("Failed to execute git command. Printing some diagnostic info...", exc_info=True)
            branch = self.get_current_branch_name()
            LOG.error("Current branch: %s", branch)
            branch_tup = GitWrapper._get_branch_tuple(branch)
            git_branches_arg = "{}..{}".format(branch_tup[0], branch_tup[1])
            git_log_out = self.repo.git.execute(["git", "log", git_branches_arg])
            LOG.error("Git commit diff between branches: %s: %s", git_branches_arg, git_log_out)

    @staticmethod
    def _get_branch_tuple(branch):
        remote_br = ORIGIN + "/" + branch
        return branch, remote_br

    def checkout_and_pull(self, checkout_ref, remote_to_pull=ORIGIN, no_ff=False, ff_only=False):
        pull_kwargs = {}
        if no_ff:
            pull_kwargs["no-ff"] = True
        if ff_only:
            pull_kwargs["ff-only"] = True

        self.checkout_branch(checkout_ref)
        LOG.info(f"Pulling {remote_to_pull}")
        self.repo.remotes[remote_to_pull].pull(**pull_kwargs)

    def fetch(self, repo_url=None, remote_name=None, all=False):
        progress = ProgressPrinter("fetch")
        if not repo_url and not remote_name and not all:
            raise ValueError("Please specify remote or use the 'all' switch")

        if repo_url:
            try:
                LOG.info("Fetching from provided repo URL: %s", repo_url)
                self.repo.git.fetch(repo_url, remote_name)
                return True
            except GitCommandError:
                LOG.exception("Git fetch failed.", exc_info=True)
                return False

        if all:
            LOG.info("Fetching all remotes of git repo '%s'...", self.repo_path)
            for remote in self.repo.remotes:
                LOG.info("Fetching remote '%s' of repository: %s", remote, self.repo.git_dir)
                remote.fetch()
        else:
            LOG.info("Fetching remote '%s' of repository: %s", remote_name, self.repo.git_dir)
            remote = self.repo.remote(name=remote_name)
            remote.fetch(progress=progress)

    def checkout_previous_branch(self):
        prev_branch = self.get_current_branch_name()
        self.repo.git.checkout("-")
        LOG.info("Checked out: %s (Previous branch was: %s)", self.get_current_branch_name(), prev_branch)

    def rebase(self, rebase_onto):
        LOG.info("Rebasing onto branch: %s", rebase_onto)

        try:
            self.repo.git.rebase(rebase_onto)
        except GitCommandError:
            LOG.exception("Rebase failed!", exc_info=True)
            try:
                self.abort_rebase()
                LOG.error("Rebase was aborted! Please rebase manually!")
            except GitCommandError as e2:
                LOG.debug("Rebase was not in progress, but probably this is normal. Exception data: %s", e2)
            return False

        return True

    def abort_rebase(self):
        LOG.info("Aborting rebase...")
        self.repo.git.rebase(abort=True)

    def diff_check(self, raise_exception=True):
        try:
            self.repo.git.diff(check=True)
            return True
        except GitCommandError as e:
            LOG.error("Git diff --check failed. There are trailing whitespaces in the diff, please fix them!")
            if raise_exception:
                raise e
            return False

    def apply_check(self, patch, raise_exception=False):
        try:
            self.repo.git.apply(patch, check=True)
            return True
        except GitCommandError as e:
            LOG.exception("Git apply --check failed", exc_info=True)
            if raise_exception:
                raise e
            return False

    def apply_patch(self, patch, include_check=True, raise_exception=False):
        try:
            if include_check:
                self.apply_check(patch, raise_exception=False)
            LOG.info("Applying patch: %s", patch)
            self.repo.git.apply(patch)
            return True
        except GitCommandError as e:
            LOG.error("Git apply failed for patch %s!", patch)
            if raise_exception:
                raise e
            return False

    def apply_patch_advanced(self, patch: AdvancedJiraPatch, branch_prefix):
        if not isinstance(patch, AdvancedJiraPatch):
            raise ValueError("patch must be an instance of JiraPatch!")
        if not self.repo:
            raise ValueError("Repository is not yet synced! Please invoke sync_hadoop method before this method!")

        LOG.info("Applying patch %s on branches: %s", patch.filename, patch.target_branches)
        LOG.debug("Applying patch %s", patch)

        results = []
        for branch in patch.target_branches:
            patch_branch_name = "{prefix}-{branch}-{filename}".format(
                prefix=branch_prefix, branch=branch, filename=patch.filename
            )
            target_branch = "origin/" + branch

            if not patch.is_applicable_for_branch(branch):
                LOG.warning(
                    "Patch %s is not applicable on branch %s! Reason: %s!",
                    patch,
                    branch,
                    patch.get_reason_for_non_applicability(branch),
                )
                results.append(PatchApply(patch, target_branch, JiraPatchStatus.PATCH_ALREADY_COMMITTED))
                continue

            # If branch already exists, move it to target_branch
            if patch_branch_name in self.repo.heads:
                LOG.info(
                    "Patch branch already exists with name %s, moving branch pointer to %s",
                    patch_branch_name,
                    target_branch,
                )
                patch_branch = self.repo.heads[patch_branch_name]
                patch_branch.set_commit(target_branch)
            else:
                patch_branch = self.repo.create_head(patch_branch_name, target_branch)

            self.repo.head.reference = patch_branch
            self.cleanup()
            try:
                LOG.debug("[%s] Applying patch %s to branch: %s...", patch.issue_id, patch.filename, target_branch)
                status, stdout, stderr = self.repo.git.execute(
                    ["git", "apply", patch.file_path], with_extended_output=True
                )
                self.log_git_exec(status, stderr, stdout)
                if status == 0:
                    LOG.info(
                        "[%s] Successfully applied patch %s to branch: %s.",
                        patch.issue_id,
                        patch.filename,
                        target_branch,
                    )
                    results.append(PatchApply(patch, target_branch, JiraPatchStatus.APPLIES_CLEANLY))
                else:
                    LOG.error("Something bad happened")
                    self.log_git_exec(status, stderr, stdout, level=logging.INFO)
            except GitCommandError as gce:
                if "patch does not apply" in gce.stderr:
                    LOG.info("[%s] Patch %s does not apply to %s!" % (patch.issue_id, patch.filename, target_branch))
                    self.log_git_exec(gce.status, gce.stderr, gce.stdout)

                    conflicts = GitUtils.get_number_of_conflicts_from_str(gce.stderr)
                    results.append(
                        PatchApply(
                            patch,
                            target_branch,
                            JiraPatchStatus.CONFLICT,
                            conflicts=conflicts,
                            conflict_details=gce.stderr,
                        )
                    )
                else:
                    results.append(PatchApply(patch, target_branch, JiraPatchStatus.UNKNOWN_ERROR))

        return results

    def validate_branches(self, branches):
        if not self.repo:
            raise ValueError("Repository is not yet synced! Please invoke sync_hadoop method before this method!")
        for branch in branches:
            Repo.rev_parse(self.repo, "origin/" + branch)

    def cleanup(self):
        self.repo.head.reset(index=True, working_tree=True)
        self.repo.git.clean("-xdfq")

    def log_git_exec(self, status, stderr, stdout, level=logging.DEBUG):
        if level == logging.DEBUG:
            LOG.debug("Status of git command: %s", status)
            LOG.debug("stdout of git command: %s", stdout)
            LOG.debug("stderr of git command: %s", stderr)
        else:
            LOG.info("Status of git command: %s", status)
            LOG.info("stdout of git command: %s", stdout)
            LOG.info("stderr of git command: %s", stderr)

    def get_commit_hashes(self, issue_id, branch=None):
        cmd_list = ["git", "log"]
        basic_options = ["--oneline", "--grep", issue_id]
        if branch:
            cmd_list.append(branch)
        else:
            cmd_list.append("--all")
        cmd_list.extend(basic_options)

        status, stdout, stderr = self.repo.git.execute(cmd_list, with_extended_output=True)
        self.log_git_exec(status, stderr, stdout)
        if status != 0:
            raise ValueError("[%s] Failed to run git log command that finds a Jira issue!")
        if stdout:
            commit_hashes = []
            for line in stdout.splitlines():
                line_parts = line.split(" ")
                if len(line_parts) > 0:
                    commit_hashes.append(line_parts[0])
            return commit_hashes

        return []

    def get_remote_branches_for_commits(self, commits, strip_remote=True):
        if commits is None:
            raise ValueError("List of commits should not be None!")

        remote_branches = []
        for commit in commits:
            status, stdout, stderr = self.repo.git.execute(
                ["git", "branch", "-r", "--contains", commit], with_extended_output=True
            )
            self.log_git_exec(status, stderr, stdout)
            if status != 0:
                raise ValueError("[%s] Failed to run git branch command that finds remote branches for commit!")
            if stdout:
                for r_branch in stdout.splitlines():
                    if len(r_branch) > 0:
                        stripped_rbranch = r_branch.lstrip()

                        if strip_remote:
                            local_branch = GitUtils.convert_remote_branch_name_to_local(r_branch)
                            remote_branches.append(local_branch)
                        else:
                            remote_branches.append(stripped_rbranch)
            else:
                return []
        return remote_branches

    def diff(self, branch, cached=False):
        kwargs = {}
        if cached:
            kwargs["cached"] = True

        LOG.info("Making diff against %s", branch)
        return self.repo.git.diff(branch, **kwargs)

    def diff_between_refs(self, ref1, ref2):
        LOG.info("Making diff: %s..%s", ref1, ref2)
        return self.repo.git.diff(f"{ref1}..{ref2}")

    def diff_tree(self, ref, no_commit_id=None, name_only=None, recursive=False):
        args = [ref]

        kwargs = {}
        if no_commit_id:
            kwargs["no_commit_id"] = True
        if name_only:
            kwargs["name_only"] = True
        if recursive:
            kwargs["r"] = True

        if not self.is_enabled_git_cmd_logging:
            LOG.info("Running git diff-tree with arguments, args: %s, kwargs: %s", args, kwargs)
        diff_tree_results = self.repo.git.diff_tree(*args, **kwargs).splitlines()
        return diff_tree_results

    def show(self, hash, no_patch=None, no_notes=None, pretty=None, suppress_diff=False, format=None):
        args = [hash]

        kwargs = {}
        if no_patch:
            kwargs["no_patch"] = True
        if no_notes:
            kwargs["no_notes"] = True
        if pretty:
            kwargs["pretty"] = pretty
        if suppress_diff:
            kwargs["s"] = True
        if format:
            kwargs["format"] = format

        if not self.is_enabled_git_cmd_logging:
            LOG.info("Running git show with arguments, args: %s, kwargs: %s", args, kwargs)
        result = self.repo.git.show(*args, **kwargs).splitlines()
        return result

    def get_author_by_hash(self, hash):
        return self.show(hash, suppress_diff=True, format="%ae")

    def is_working_directory_clean(self):
        status = self.repo.git.status(porcelain=True)
        LOG.debug("Git status: %s", status)
        return False if len(status) > 0 else True

    def is_branch_exist(self, branch: str, exc_info=True):
        try:
            self.repo.git.rev_parse("--verify", branch)
            return True
        except GitCommandError:
            LOG.exception("Branch does not exist", exc_info=exc_info)
            return False

    def list_branches(self, name):
        try:
            branches = self.repo.git.branch("--list", name)
            branches = branches.split("\n")
            return [b.replace(" ", "") for b in branches]
        except GitCommandError:
            LOG.exception(f"Branch does not exist with name: {name}", exc_info=True)
            return []

    def add_all_and_commit(self, commit_msg, raise_exception=False):
        try:
            self.repo.git.add("-A")
            self.repo.index.commit(commit_msg)
            return True
        except GitCommandError:
            LOG.exception("Failed to commit changes from index", exc_info=True)
            return False

    def commit(
        self, message, author: Actor = None, committer: Actor = None, add_files_to_index: List[str] = None, amend=False
    ):
        if not add_files_to_index:
            add_files_to_index = []

        kwargs = {}
        if amend:
            kwargs["amend"] = amend
        if author:
            kwargs["author"] = author
        if committer:
            kwargs["committer"] = committer
        LOG.info("Running git commit with arguments: %s", kwargs)

        if add_files_to_index:
            self.add_to_index(add_files_to_index)
        self.repo.index.commit(message, **kwargs)

    def log(
        self,
        revision_range,
        oneline=False,
        oneline_with_date=False,
        oneline_with_date_and_author=False,
        oneline_with_date_author_committer=False,
        grep=None,
        format=None,
        n=None,
        return_hashes=False,
        return_messages=False,
        as_string_message=False,
        follow=False,
        all=False,
        grep_first_line_only=False,
    ):
        # TODO Raise error if any of oneline_with_date, oneline_with_date_and_author, oneline_with_date_author_committer
        # are True at the same time
        if oneline and oneline_with_date:
            raise ValueError("oneline and oneline_with_date should be exclusive!")

        if as_string_message and n != 1:
            raise ValueError("as_string_message only works with option n=1")

        args = []
        if revision_range:
            args.append(revision_range)

        kwargs = {}
        if oneline:
            kwargs["oneline"] = True

        # https://git-scm.com/docs/pretty-formats
        # Oneline format: <hash> <title line>
        # Oneline + date format: <hash> <title line> <author date>
        if oneline_with_date:
            kwargs["format"] = f"{FORMAT_CODE_HASH} {FORMAT_CODE_COMMIT_MSG} {FORMAT_CODE_DATE_ISO_8601}"
        if oneline_with_date_and_author:
            kwargs[
                "format"
            ] = f"{FORMAT_CODE_HASH} {FORMAT_CODE_COMMIT_MSG} {FORMAT_CODE_DATE_ISO_8601} {FORMAT_CODE_AUTHOR}"
        if oneline_with_date_author_committer:
            kwargs[
                "format"
            ] = f"{FORMAT_CODE_HASH} {FORMAT_CODE_COMMIT_MSG} {FORMAT_CODE_DATE_ISO_8601} {FORMAT_CODE_AUTHOR} {FORMAT_CODE_COMMITTER}"
        if format:
            kwargs["format"] = format
        if grep:
            kwargs["grep"] = grep
        if n:
            kwargs["n"] = n
        if follow:
            kwargs["follow"] = True
        if all:
            kwargs["all"] = True

        if not self.is_enabled_git_cmd_logging:
            LOG.info("Running git log with arguments, args: %s, kwargs: %s", args, kwargs)
        log_result = self.repo.git.log(*args, **kwargs).splitlines()

        if grep and grep_first_line_only and grep not in log_result:
            log_result = []

        if return_hashes:
            return [result.split(COMMIT_FIELD_SEPARATOR)[0] for result in log_result]
        if return_messages:
            # Remove commit hash and rejoin parts of commit message into one string
            # TODO Below command only works for --oneline option
            return [COMMIT_FIELD_SEPARATOR.join(result.split(COMMIT_FIELD_SEPARATOR)[1:]) for result in log_result]

        if as_string_message:
            return "\n".join(log_result)
        return log_result

    def branch(self, refspec, recursive=False, contains=None):
        args = []
        if refspec:
            args.append(refspec)

        kwargs = {}
        if recursive:
            kwargs["r"] = True
        if contains:
            kwargs["contains"] = contains

        lines = self.repo.git.branch(refspec, *args, **kwargs).splitlines()
        for idx, line in enumerate(lines):
            # Replace all whitespace with empty string
            lines[idx] = "".join(line.split())
        return lines

    def cherry_pick(self, ref, x=False):
        kwargs = {}
        if x:
            kwargs["x"] = x
        try:
            self.repo.git.cherry_pick(ref, **kwargs)
            return True
        except GitCommandError:
            LOG.exception("Failed to cherry-pick commit: " + ref, exc_info=True)
            return False

    def format_patch(self, revision_range, output_dir=None, full_index=None):
        # git format-patch ${GIT_BASE_BRANCH} --output-directory ${GIT_FORMAT_PATCH_OUTPUT_DIR} --full-index
        args = []
        if revision_range:
            args.append(revision_range)

        kwargs = {}
        if output_dir:
            kwargs["output_directory"] = output_dir
        if full_index:
            kwargs["full_index"] = True

        if not self.is_enabled_git_cmd_logging:
            LOG.info("Running git format-patch with arguments, args: %s, kwargs: %s", args, kwargs)
        return self.repo.git.format_patch(*args, **kwargs)

    def rewrite_head_commit_message(self, prefix=None, postfix=None):
        if not prefix and not postfix:
            raise ValueError("You must provide either prefix or postfix!")
        old_commit_msg = self.get_head_commit_message()
        # Add downstream (CDH jira) number as a prefix.
        # Since it triggers a commit, it will also add gerrit Change-Id to the commit.
        self.repo.git.commit(amend=True, message=f"{prefix}{old_commit_msg}")

    def merge_base(self, feature_br: str, master_br: str) -> List[Commit]:
        return self.repo.merge_base(feature_br, master_br)

    def get_head_commit_message(self):
        return self.log(HEAD, format="%B", n=1, as_string_message=True)

    def get_commit_message_of_branch(self, branch):
        # TODO error handling if branch does not exist
        commit = self.repo.heads[branch].commit
        actual_commit_message = commit.message.rstrip()
        return actual_commit_message

    @staticmethod
    def extract_commit_hash_from_gitlog_results(results):
        return [res.split(COMMIT_FIELD_SEPARATOR)[0] for res in results]

    @staticmethod
    def extract_commit_hash_from_gitlog_result(result):
        return result.split(COMMIT_FIELD_SEPARATOR)[0]

    def reset_changes(self, reset_to=DEFAULT_BRANCH, reset_index=True, reset_working_tree=True, clean=True):
        LOG.info(f"Reset all changes. Params: {locals()}")
        self.repo.head.reset(commit=reset_to, index=reset_index, working_tree=reset_working_tree)
        if clean:
            self.repo.git.clean("-xdf")

    def reset(self, hard=False):
        if hard:
            self.repo.git.reset("--hard")
        else:
            self.repo.git.reset()

    def setup_committer_info(self, user, email):
        self.repo.config_writer().set_value("user", "name", user).release()
        self.repo.config_writer().set_value("user", "email", email).release()

    def remove_committer_info(self):
        self.repo.config_writer().set_value("user", "name", "").release()
        self.repo.config_writer().set_value("user", "email", "").release()

    def setup_pull_mode_ff_only(self, global_mode=False):
        config_level = self._get_git_config_level(global_mode)
        self.repo.config_writer(config_level=config_level).set_value("pull", "ff", "only").release()

    def read_config(self, global_mode=False):
        config_level = self._get_git_config_level(global_mode)
        conf_reader = self.repo.config_reader(config_level)
        conf_reader.read()
        self._safe_get_config_section(conf_reader, "pull", config_level)
        self._safe_get_config_section(conf_reader, "push", config_level)

    @staticmethod
    def _safe_get_config_section(conf_reader, section_name, config_level):
        try:
            conf = conf_reader.items_all(section_name)
            LOG.info("Git config for section '%s': %s", section_name, conf)
            return conf
        except KeyError:
            LOG.warning("Section '%s' does not exist in Git config. Config mode: %s", section_name, config_level)

    @staticmethod
    def _get_git_config_level(global_mode: bool):
        config_level = "repository"
        if global_mode:
            config_level = "global"
        return config_level

    def add_remote(self, name, url):
        try:
            self.repo.create_remote(name, url=url)
        except GitCommandError:
            # TODO make swallowing exception optional
            pass

    def remove_remote(self, name):
        self.repo.delete_remote(name)

    def get_hash_of_commit(self, branch):
        return self.repo.heads[branch].commit.hexsha

    def checkout_parent_of_branch(self, branch):
        if branch not in self.repo.heads:
            raise ValueError(f"Cannot find branch: {branch}")
        self.repo.git.checkout(branch + "^")
        return self.repo.git.rev_parse("--verify", HEAD)

    def get_all_branch_names(self):
        return [br.name for br in self.repo.heads]

    def remove_branches_with_prefix(self, prefix, checkout_before_remove=DEFAULT_BRANCH):
        branches = self.get_all_branch_names()
        matching_branches = list(filter(lambda br: br.startswith(prefix), branches))

        for branch in matching_branches:
            self.remove_branch(branch, checkout_before_remove=checkout_before_remove)

    def remove_branch(self, branch, ignore_error=True, checkout_before_remove=DEFAULT_BRANCH):
        LOG.info("Removing branch: %s", branch)
        # Checkout default branch, in case of branch is currently checked out
        self.checkout_branch(checkout_before_remove)

        try:
            self.repo.delete_head(branch, force=True)
        except GitCommandError as e:
            if not ignore_error:
                raise e

    def add_to_index(self, items: List[str]):
        LOG.debug(f"Adding files to index: {items}")
        self.repo.index.add(items)

    def __str__(self):
        filtered_dict = dict(filter(lambda elem: elem[0] in ["repo_path"], vars(self).items()))
        return "%s(%s)" % (type(self).__name__, ", ".join("%s=%s" % item for item in filtered_dict.items()))


class ProgressPrinter(RemoteProgress):
    def __init__(self, operation):
        super(ProgressPrinter, self).__init__()
        self.operation = operation

    def update(self, op_code, cur_count, max_count=None, message=""):
        percentage = cur_count / (max_count or 100.0) * 100
        LOG.info("Progress of git %s: %s%% (speed: %s)", self.operation, percentage, message or "-")
