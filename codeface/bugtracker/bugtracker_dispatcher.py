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

"""
Dispatcher module to coordinate worker processes, the queue, and jobs.
"""

import pkgutil
from multiprocessing import Manager

import codeface.bugtracker.scraper as scraperpkg
import codeface.bugtracker.scraper.bugzilla as bugzilla
import codeface.util as utility
from codeface.configuration import Configuration
from codeface.dbmanager import DBManager
from codeface.cluster.idManager import idManager

# TODO Check the cli interface so that it works perfectly


def bt_analyse(codeface_conf, bt_conf, ct, cachedir, logfile, flags, j):
    """Main runner function for the bugtracker analysis.

    Uncrates the config file and utilizes the flags to control the executed
    steps. Further handles output and pacing.

    Args:
        codeface_conf(str): codeface configuration file, contains:

        bt_conf(str): Bugtracker/project configuration file, contains:
            bug_project_name: name of the project to be analysed
            bugtracker_type: type of the bugtracker
            bugtracker_url: initial url for the bugtracker
            project_id: id for the REST for all bugs belonging to a project
        ct(str): cache type, currently valid ones are: fs
        cachedir(str):
        logfile(str): Logging file
        flags(tuple): Configuration flags
        j(int): Number of simultaneos jobs

    Returns:

    Notes:
        db cachetype is currently not implemented

    """
    # Init config, database, ID service and the dispatcher objects
    conf = Configuration.load(codeface_conf, bt_conf)
    database = DBManager(conf)
    id_manager = idManager(database, conf)
    dispatcher = BugtrackerDispatcher(conf, id_manager, database, j)

    # Check if bugtracker type is valid, and perform one-off operations
    if not bt_type_is_valid(conf["bugtracker_type"]):
        raise Exception("Bugtracker type not supported, aborting!")
    if conf["bugtracker_type"] == "bugzilla":
        bugzilla.init_first_url(dispatcher.url_queue, conf)

    # If the transform-only or parse-only flag is not set, scrape the target
    if not flags[2]:
        dispatcher.scrape_target(cachedir)
        # After this is done, we should have a cache full of serialised raw data
        # which can be JSON objects, plain strings or something else bugtracker
        # specific

    if not flags[1]:
        dispatcher.parse_target()
        # After this is done, the database has been filled
    return


def bt_type_is_valid(bugtracker_type):
    """
    Validates the bugtracker type, returns true if corresponding module
    exists
    Args:
        bugtracker_type(str): Bugtracker type - currently valid types are
            generic and bugzilla

    Returns:
         bool:

    """
    list_of_valid_scrapers = list()
    # Only the module name is interesting
    for _, modname, _ in pkgutil.walk_packages(path=scraperpkg.__path__):
        list_of_valid_scrapers.append(modname)

    if bugtracker_type in list_of_valid_scrapers:
        return True
    else:
        return False


class BugtrackerDispatcher(object):
    """Class for dispatching the bugtracker logic."""

    def __init__(self, conf, id_manager, database, j):
        super(BugtrackerDispatcher, self).__init__()
        # Spawn instance variables
        self.manager = Manager()
        self.url_dict = self.manager.dict()
        self.url_queue = self.manager.Queue()
        self.pool = utility.BatchJobPool(j)
        self.conf = conf
        self.database = database
        self.id_manager = id_manager
        self.results = self.manager.dict()

    def scrape_target(self, cachedir):
        # TODO replace with pool call
        if self.conf["bugtracker_type"] is "bugzilla":
            bugzilla.scrape(self.url_queue, self.conf, self.results, cachedir)
        # Add elifs for additional bugtracker types here

    def parse_target(self):
        # TODO Replace with pool call
        for handle in self.results.items():
            if self.conf["bugtracker_type"] is "bugzilla":
                bugzilla.parse(handle, self.database, self.id_manager)
        # Add elifs for additonal bugtracker types here
