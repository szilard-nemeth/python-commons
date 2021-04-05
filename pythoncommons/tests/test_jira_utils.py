import os
import unittest
from os.path import expanduser

from pythoncommons.file_utils import FileUtils
from pythoncommons.jira_utils import JiraUtils
from pythoncommons.project_utils import ProjectUtils

PROJECT_NAME = "pythoncommons"


class JiraUtilsTests(unittest.TestCase):
    def test_YARN_10496(self):
        project_out_root = ProjectUtils.get_test_output_basedir(PROJECT_NAME)
        result_basedir = FileUtils.join_path(project_out_root, "jira-data")
        FileUtils.ensure_dir_created(result_basedir)
        jira_id = "YARN-10496"
        jira_html_file = FileUtils.join_path(result_basedir, "jira.html")
        jira_list_file = FileUtils.join_path(result_basedir, "jira-list.txt")

        jira_html = JiraUtils.download_jira_html(
            "https://issues.apache.org/jira/browse/", jira_id, jira_html_file
        )
        jira_ids_and_titles = JiraUtils.parse_subjiras_and_jira_titles_from_umbrella_html(
            jira_html, jira_list_file, filter_ids=[jira_id]
        )

        expected_jira_ids = ['YARN-10169', 'YARN-10504', 'YARN-10505', 'YARN-10506', 'YARN-10512', 'YARN-10513',
                             'YARN-10521', 'YARN-10522', 'YARN-10524', 'YARN-10525', 'YARN-10531', 'YARN-10532',
                             'YARN-10535', 'YARN-10564', 'YARN-10565', 'YARN-10571', 'YARN-10573', 'YARN-10574',
                             'YARN-10576', 'YARN-10577', 'YARN-10578', 'YARN-10579', 'YARN-10581', 'YARN-10582',
                             'YARN-10583', 'YARN-10584', 'YARN-10587', 'YARN-10590', 'YARN-10592', 'YARN-10596',
                             'YARN-10598', 'YARN-10599', 'YARN-10600', 'YARN-10604', 'YARN-10605', 'YARN-10609',
                             'YARN-10614', 'YARN-10615', 'YARN-10620', 'YARN-10622', 'YARN-10624']
        all_list_items_found = all(id1 in jira_ids_and_titles.keys() for id1 in expected_jira_ids)
        self.assertTrue(all_list_items_found)

        expected_mappings = {'YARN-10624': 'Support max queues limit configuration in new auto created queue, consistent with old auto created.'}
        self.assertEqual(expected_mappings['YARN-10624'], jira_ids_and_titles['YARN-10624'])
        self.assertTrue(isinstance(jira_ids_and_titles['YARN-10624'], str))

