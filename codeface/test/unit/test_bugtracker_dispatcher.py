# This file is part of Codeface. Codeface is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Copyright 2013 by Siemens AG, Johannes Ebke <johannes.ebke.ext@siemens.com>
# All Rights Reserved.

# Currently deactivated due to not using true temporary files
# see: https://github.com/siemens/codeface/commit/
# 070ddf7fc46da4aeccebcd54d69bb122bde46e4b
# Also it does not entirely work during vagrant setup


# import os
# import unittest
# from Queue import Queue
# from logging import getLogger
#
# import codeface.bugtracker.scraper.bugzilla as bugzilla
# import codeface.bugtracker.filesystem_cache as syscache
# # Import this to prevent logging errors
# import codeface.logger
#
# from codeface.cluster.idManager import idManager
# from codeface.configuration import Configuration
# from codeface.bugtracker.bugtracker_dispatcher import BugtrackerDispatcher
# from codeface.dbmanager import DBManager
#
# log = getLogger(__name__)
#
#
#
# class TestBugtrackerDispatcher(unittest.TestCase):
#     """Test the bugtracker dispacher.
#
#     Tests file system cache, bugtracker dispatcher, scrape and parse
#     functionality. Currently runs against the Composer Mozilla sub-project.
#     """
#
#     def setUp(self):
#         """Setting up, including Configuration and database connections"""
#         log.info("Setting up test environment")
#         global_conf = os.path.abspath("../../../codeface.conf")
#         bt_conf = os.path.abspath("../../../conf/mozilla_composer.conf")
#         conf = Configuration.load(global_conf, bt_conf)
#         database = DBManager(conf)
#         id_manager = idManager(database, conf)
#         self.dispatcher = BugtrackerDispatcher(conf, id_manager, database)
#         self.url_storage_list = list()
#
#     def tearDown(self):
#         """Teardown, removing cache directory"""
#         log.info("Tearing down test environment")
#         log.debug("Removing cache directory")
#         for root, dirs, files in os.walk("cache", topdown=False):
#             for name in files:
#                 os.remove(os.path.join(root, name))
#             for name in dirs:
#                 os.rmdir(os.path.join(root, name))
#
#     def fs_cache_test(self):
#         """Test the file system cache by storing and retrieving data"""
#         target_dir = syscache.compute_path("cache", "buglib")
#         log.info("Storage target is {target}".format(target=target_dir))
#
#         syscache.put_in_cache("test_data", 42, "cache")
#         comparison = syscache.get_from_cache("test_data", "cache")
#         self.assertTrue(comparison == 42)
#
#     def bugzilla_test_scrape(self):
#         """Test scraping target bugs to cache"""
#         log.info("Retrieving bugIDs")
#         bugzilla.init_first_url(self.dispatcher.url_queue,
#                                 self.url_storage_list,
#                                 self.dispatcher.conf)
#
#         log.info("Scraping remote")
#         self.dispatcher.scrape_target("cache", 1)
#
#         log.info("Counting files in cache")
#         num_files = 0
#         for root, dirs, files in os.walk("cache"):
#             for target_file in files:
#                 num_files += 1
#
#         # All bugs retrieved
#         self.assertEqual(num_files, len(self.url_storage_list))
#
#     def test_bug_id_cache(self):
#         """Test caching of bug ID lists and queues"""
#         log.info("Procuring list of bug IDs")
#         bugzilla.init_first_url(self.dispatcher.url_queue,
#                                 self.url_storage_list,
#                                 self.dispatcher.conf)
#
#         log.debug("Storing list in cache")
#         syscache.put_in_cache("buglist", self.url_storage_list, "cache")
#
#         log.debug("Restoring list from cache")
#         restored_list = syscache.get_from_cache("buglist", "cache")
#         log.debug("Checking equality")
#         self.assertListEqual(self.url_storage_list, restored_list)
#
#         log.info("Rebuilding bug queue from cache")
#         restored_queue = Queue()
#         for item in restored_list:
#             restored_queue.put(item)
#         log.debug("Asserting queue equality")
#         while not self.dispatcher.url_queue.empty():
#             self.assertEqual(self.dispatcher.url_queue.get(),
#                              restored_queue.get())
#
#     def test_parse(self):
#         """Test parser, writing to the id_service and database"""
#         log.info("Procuring some bugs/IDs to parse")
#         bugzilla.init_first_url(self.dispatcher.url_queue,
#                                 self.url_storage_list,
#                                 self.dispatcher.conf)
#
#         result_dict = dict()
#         bugzilla.scrape(self.dispatcher.url_queue, self.dispatcher.conf,
#                         result_dict, "cache")
#
#         log.info("Parsing procured material")
#         bugzilla.parse(result_dict,
#                        self.dispatcher.database, self.dispatcher.id_manager, 14)
#         bugzilla.create_dependencies(result_dict, self.dispatcher.database)
#
#     def test_scraper_error(self):
#         """Test scaper error handling when encountering strange chars"""
#         # Switch project to Firefox and insert bug with known forbidden char
#         self.dispatcher.conf["project_id"] = "firefox"
#         self.dispatcher.url_queue.put(840976)
#         bugzilla.scrape(self.dispatcher.url_queue, self.dispatcher.conf,
#                         self.dispatcher.results, "cache")
