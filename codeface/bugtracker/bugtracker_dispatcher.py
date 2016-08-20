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
Dispatcher module to coordinate worker processes, the queue, and jobs. Also to
route the to the correct bugtacker module.
"""

import pkgutil
import os
import gc
from multiprocessing import Manager
from logging import getLogger

import codeface.bugtracker.scraper as scraperpkg
import codeface.bugtracker.scraper.bugzilla as bugzilla
import codeface.bugtracker.filesystem_cache as syscache
from codeface.configuration import Configuration
from codeface.dbmanager import DBManager
from codeface.cluster.idManager import idManager
from codeface.util import BatchJobPool

log = getLogger(__name__)


def bt_analyse(codeface_conf, bt_conf, cachedir, logfile, flags, jobs):
    """Main function for the bugtracker analysis.

    Loads the configuration using codeface.configuration, then creates all
    instances necessary for for running the bugtracker scraper.
    Also serves as attachment point for those objects, especially using an
    instance of BugtrackerDispatcher for coordinating the managed queues and
    dicts.

    Args:
        codeface_conf(str): Path to codeface configuration file
        bt_conf(str):Path to  Bugtracker/project configuration file, contains:
            bug_project_name: name of the project to be analysed
            bugtracker_type: type of the bugtracker,e.g. bugzilla
            bugtracker_url: root url used for the queries
            project_id: key for the project queried
        cachedir(str): Absolute directory of the filesystem cache
        logfile(str): Path to logging file
        flags(tuple): Configuration flags. The flags consist of:
            ct(str): cache type (valid are: fs, None, db)
            so(bool): scrape-only flag
            po(bool): parse-only flag
            cont(bool): continue flag, continue building a partial cache
            discard(bool): Discard the database, then exit
            asProject(bool): Enable product as project treatment
        jobs(int): Number of parallel processes for the scrape

    Notes:
        Only filesystem cache is currently supported

    """
    # Init config, database, ID service and the dispatcher object
    conf = Configuration.load(codeface_conf, bt_conf)
    database = DBManager(conf)
    id_manager = idManager(database, conf)
    dispatcher = BugtrackerDispatcher(conf, id_manager, database)

    # Discard flag found, dump the database - requires a database connection
    if flags[4]:
        log.info("Dumping database, exiting")
        database.reset_bugtracker_database()
        exit(0)

    # jobs is initialized as string and are converted to int
    log.debug("BatchPool will have a size of {size}".format(size=jobs))
    jobs = int(jobs)

    # Check if bugtracker type is valid, if not abort
    log.info("Validating bugtracker type")
    if not bt_type_is_valid(conf["bugtracker_type"]):
        log.critical("Bugtracker type {type} not supported!".
                     format(type=conf["bugtracker_type"]))
        raise Exception("Bugtracker type not supported, aborting!")

    # Create/query project ID in database
    database_pid = database.getProjectID(conf["project_id"], "bugtracker")
    log.info("{pro} was assigned PID {pid}".format(pro=conf["project_id"],
                                                   pid=database_pid))

    # Perform one-time operations specific to certain bugtrackers
    # For bugzilla, this is frontloading the bug id list
    if (conf["bugtracker_type"] == "bugzilla") and (not flags[2]):
        log.info("Performing one-time operations for bugzilla")
        url_storage_list = list()
        bugzilla.init_first_url(dispatcher.url_queue, url_storage_list, conf)
        log.info("{nr} bugs waiting for scrape".
                 format(nr=dispatcher.url_queue.qsize()))
        syscache.put_in_cache("buglist", url_storage_list, cachedir)
        log.info("List of bugIDs stored in cache")

    # Continue flag is set, determine what bugs are in the cache,
    # build a new work queue from those that aren't
    if flags[3]:
        log.info("Determining bugs already in cache")
        while not dispatcher.url_queue.empty():
            current_id = dispatcher.url_queue.get()
            log.debug("Checking bug {nr}".format(nr=str(current_id)))
            if os.path.exists(os.path.dirname(
                        syscache.compute_path(cachedir, str(current_id)))):
                continue
            else:
                dispatcher.reserve_queue.put(current_id)
        dispatcher.url_queue = dispatcher.reserve_queue
        log.info("{nr} bugs remaining to be scraped".
                 format(nr=str(dispatcher.url_queue.qsize())))

    # Start the scrape, discard all unused objects by calling the GC beforehand
    gc.collect()
    if not flags[2]:
        log.info("Starting scrape")
        dispatcher.scrape_target(cachedir, jobs)

    # Discard all unused objects to avoid nasties
    gc.collect()
    # If parse only is set, load the bugIDs from the cache
    # and restore the result dict
    if flags[2]:
        log.info("Retrieving bug IDs from cache")
        saved_url_list = syscache.get_from_cache("buglist", cachedir)
        for item in saved_url_list:
            try:
                dispatcher.results[item] = syscache.get_from_cache(str(item), cachedir)
            except IOError:
                log.debug("Bug ID {nr} is not in the cache, skipping".
                          format(nr=str(item)))
                dispatcher.results.pop(item, None)
            except EOFError:
                log.critical("{id} cache corrupted, skipping".format(id=item))
                pass

    gc.collect()
    # Start the parse
    if not flags[1]:
        log.info("Starting parse")
        dispatcher.parse_target(database_pid, flags[5])

    return


def bt_type_is_valid(bugtracker_type):
    """Validates the bugtracker type

    Args:
        bugtracker_type(str): Bugtracker type - currently valid types are
            generic and bugzilla

    Returns:
         bool: Whether the type is valid

    Note:
        The file name MUST be equivalent to the project id in the project
        configuration file
    """
    # Init locals
    list_of_valid_scrapers = list()
    # Only the module name is of interest
    for _, modname, _ in pkgutil.walk_packages(path=scraperpkg.__path__):
        list_of_valid_scrapers.append(modname)

    if bugtracker_type in list_of_valid_scrapers:
        return True
    else:
        return False


class BugtrackerDispatcher(object):
    """Container class for multiprocessing queues and dicts for bt analysis"""

    def __init__(self, conf, id_manager, database):
        super(BugtrackerDispatcher, self).__init__()
        # Spawn instance variables
        self.manager = Manager()
        self.url_dict = self.manager.dict()
        self.url_queue = self.manager.Queue()
        self.reserve_queue = self.manager.Queue()
        self.conf = conf
        self.database = database
        self.id_manager = id_manager
        self.results = self.manager.dict()

    def scrape_target(self, cachedir, jobs):
        """Function for scraping bug data from a remote server

        Creates a BatchJobPool with the specified size and then fills it with
        jobs appropriate to the bugtracker server being queried.

        Args:
            cachedir(str): Absolute path to the filesystem cache directory
            jobs(int): Number of jobs to run at once

        Returns (None):
        """
        job_pool = BatchJobPool(jobs)
        # Fill the pool with appropriate jobs
        for i in range(0, jobs):
            if self.conf["bugtracker_type"] == "bugzilla":
                job_pool.add(bugzilla.scrape, [self.url_queue, self.conf,
                                               self.results, cachedir])
            # NOTE: Add elifs for additional bugtracker types here
        job_pool.join()
        return

    def parse_target(self, pid, product_as_project):
        """ Indentifies and starts the parse for the relevant bugtracker.

        It fist parses the bugs and then creates the dependencies in a seperate
        step.

        Args:
            pid(int): Project identifier for/from the database
            product_as_project(bool): Flag for treating the product as a project

        Returns (None):
        """
        if self.conf["bugtracker_type"] == "bugzilla":
            id_map = bugzilla.parse(self.results, self.database,
                                    self.id_manager, pid, product_as_project)
            bugzilla.create_dependencies(self.results, self.database, id_map)
            # NOTE: Add elifs for additional bug tracker types here

        return
