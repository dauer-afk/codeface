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

"""Bugtracker crawler methods specific to the bugzilla bug tracker"""

import time
import gc
import requests
import yaml
import codeface.bugtracker.filesystem_cache as fs_cache

from logging import getLogger
from requests import ConnectionError
from yaml.reader import ReaderError
from yaml.scanner import ScannerError

log = getLogger(__name__)


def init_first_url(url_queue, storage_list, conf):
    """Initialise get the bug ids for a project.

    The query will return a dict with the single key "bugs" containing a list
    of dicts with the keys "id" and the bug IDs as values
    The function retrieves the bugs ids as chunks of 1000, due to rate and
    answer size limitations

    Args:
        storage_list (list): List object to store the bugIDs for later dump to
                            cache
        conf(codeface.configuration.Configuration): Codeface configuration file
        url_queue(multiprocessing.Queue): Multiprocessing queue to coordinate
                                        later scrape

    """
    log.info("Gathering bug IDs")
    current_offset = 0
    # Run a loop for all bug ids, incrementing by 1000 each time
    while True:
        rest_query = str(conf["bugtracker_url"] + "rest/bug?include_fields=id&"
                        "limit=1000&offset=" + str(current_offset) + "&product="
                         + conf["project_id"])
        # Query the server, if it is not there, abort
        log.debug("Querying: {target}".format(target=rest_query))
        try:
            rest_result = requests.get(rest_query)
        except requests.exceptions.ConnectionError:
            log.critical("Connection refused or unavailable")
            exit(1)

        # Response is good, continue
        if rest_result.ok:
            rest_dict = rest_result.json()
            rest_list = rest_dict["bugs"]
            if len(rest_list) == 0:
                break
            for item in rest_list:
                for key in item:
                    url_queue.put(item[key])
                    storage_list.append(item[key])
        # Go get the next 1000
        current_offset += 1000
        log.debug("Currently quering upwards of {offset}".format(
            offset=str(current_offset)))
        log.info("{nrbugs} IDs queried".format(nrbugs=str(url_queue.qsize())))

    return


def scrape(url_queue, conf, results, cachedir):
    """Query the bugs, their communication and their history from the server.

    The url_queue is threadsafe and delivers bug ids as long as as it has some.
    Store bugs in cache file.
    Store the results in the results dict, using the bug id as key.

    Args:
        cachedir (str): Absolute directory of the cache
        url_queue(multiprocessing.Queue): Queue storing the bugIDs to be
            processed
        conf(codeface.configuration.Configuration): Codeface configuration file
        results(dict): The dictionary the results are stored in

    """
    log.info("Scraping bugs")
    while not url_queue.empty():
        current_bug = url_queue.get()
        log.debug("Scraping bug number {nr}".format(nr=current_bug))
        rest_query = str(conf["bugtracker_url"] + "rest/bug/") + str(
            current_bug)
        log.debug("Current query is {qu}".format(qu=rest_query))
        try:
            current_rest = requests.get(rest_query)
        except ConnectionError:
            url_queue.put(current_bug)
            continue
        if not current_rest.ok:
            # Bad response - if it's 429 back off for a bit
            if current_rest.status_code == 429:
                log.info("Received 429 response, backing off...")
                url_queue.put(current_bug)
                time.sleep(180)
                continue
            else:
                url_queue.put(current_bug)
                continue

        # Load the JSON object from the response, if it is corrupt, skip
        try:
            current_json_dict = yaml.safe_load(current_rest.content)
        except (TypeError, ReaderError):
            log.critical("Error when reading REST response for bug {bugnr}".
                         format(bugnr=str(current_bug)))
            continue

        # Since we retrieve a single bug, open the dict and then use the first
        # element
        log.debug("Storing bug {nr} in the result list".format(nr=current_bug))
        current_dict = current_json_dict["bugs"][0]

        # Query history, if not available, discard the results and try again
        # later
        log.debug("Getting history for bug {nr}".format(nr=current_bug))
        try:
            current_rest = requests.get(conf["bugtracker_url"] + "rest/bug/" + \
                           str(current_bug) + "/history")
        except ConnectionError:
            url_queue.put(current_bug)
            continue
        try:
            current_json_dict = yaml.safe_load(current_rest.content)
        except (TypeError, ReaderError):
            continue
        history = list()
        history = current_json_dict["bugs"]
        current_dict["history"] = history

        # Do the same for communication/comments
        log.debug("Retrieving communications")
        try:
            current_rest = requests.get(conf["bugtracker_url"] + "rest/bug/" +
                                    str(current_bug) + "/comment")
        except ConnectionError:
            url_queue.put(current_bug)
            continue

        try:
            current_json_dict = yaml.safe_load(current_rest.content)
        except (ReaderError, TypeError, ScannerError, MemoryError):
            log.critical("Error when parsing comments")
            continue

        comments = list()
        comments = current_json_dict["bugs"][str(current_bug)]["comments"]
        current_dict["comments"] = comments

        # Store the completed bug information in the results dictionary
        log.debug("Storing result in dictionary")
        results[str(current_bug)] = current_dict

        # Store the bug info in the cache
        log.debug("Dumping bug {nr} to cache".format(nr=current_bug))
        fs_cache.put_in_cache(str(current_bug), current_dict, cachedir)

        # Cleanup for remaining dangling object references
        gc.collect()

    return


def parse(result_dict, db_manager, id_service, pid, product_as_project):
    """Extract the data from the object to store in the codeface DB

    Processes the JSON object to extract the necessary information for
    codefaces id service. Furthermore, the bug is preprocessed before it is
    written to the database.

    Args:
        result_dict (dict): The dict containing the JSON objects to be parsed
        db_manager (codeface.dbmanager.DBManager): Manager for the database
        id_service (codeface.cluster.idManager.idManager): id_service of
            codeface
        pid(int): project unique identifier
        product_as_project(bool): Flag for treating the product as project

    Returns dict: a list containing tuples mapping the bugIds to the databaseIDs
    """

    # TODO the bugID -> databaseID map is a dirty hack and is only present due
    # to a bug in python: issue 6766 in the python bugtracker
    # According to the bugtracker, it is fixed with the next version (at least
    # for 3.6, 2.7 patch status unknown)

    id_database_map = dict()

    # Main processing loop
    for key in result_dict.keys():
        log.debug("Processing bug {bugid}".format(bugid=str(key)))
        current_bug = result_dict[key]

        # Query the id service to create codeface ids for creator, assignee and
        # cc persons
        log.debug("Creating person IDs for emails")
        current_bug["assigned_to"] = id_service.getPersonID(
            create_id_service_email(current_bug["assigned_to_detail"]))
        current_bug["creator"] = id_service.getPersonID(
            create_id_service_email(current_bug["creator_detail"]))
        for addr in current_bug["cc_detail"]:
            addr["id"] = id_service.getPersonID(create_id_service_email(addr))

        # Create the data object for the issue table, depending on the flag
        log.debug("Putting bug into database")
        data = [key,
                current_bug["creation_time"],
                current_bug["last_change_time"],
                current_bug["url"],
                current_bug["resolution"],
                current_bug["severity"],
                current_bug["priority"],
                current_bug["creator"],
                current_bug["assigned_to"],
                pid,
                current_bug["status"]]
        if product_as_project:
            data.append(current_bug["component"])
            data.append(None)
        else:
            data.append(current_bug["product"])
            data.append(current_bug["component"])

        # Make a tuple from the list, and insert it into the database
        bug_database_id = db_manager.insert_bug(tuple(data))
        id_database_map[key] = bug_database_id
        log.debug("Database key is {nr}".format(nr=bug_database_id))

        # Populate history database
        log.debug("Inserting history")
        history_data = list()
        # One history event may contain muptiple changes, everyone gets an entry
        history = current_bug["history"][0]
        for event in history["history"]:
            for change in event["changes"]:
                history_data.append((event["when"], change["field_name"],
                                     change["removed"], change["added"],
                                     # its always an email adress, so be careful!
                                     id_service.getPersonID(event["who"]),
                                     bug_database_id))
        # History consists of at least the creation entry, but better be careful
        if len(history_data) is not 0:
            try:
                db_manager.insert_history(history_data)
            except TypeError, UnicodeEncodeError:
                log.critical("History scrape incomplete")
                pass

        # Comment database
        log.debug("Populating comment database")
        com_data = list()
        for comment in current_bug["comments"]:
            com_data.append((id_service.getPersonID(comment["author"]),
                             bug_database_id, comment["creation_time"]))
        # As above, to be on the safe side
        if len(com_data) is not 0:
            try:
                db_manager.insert_comments(com_data)
            except:
                continue

        # Write the ids into the address database
        log.debug("Populating cc adress database")
        cc_data = list()
        for addr in current_bug["cc_detail"]:
            cc_data.append((bug_database_id, addr["id"]))
        if len(cc_data) is not 0:
            db_manager.populate_cc_list(cc_data)

        # Reset containers to be on the safe side
        data = None
        del cc_data[:]
        del history_data[:]
        del com_data[:]
        # Collect the orphaned instances
        gc.collect()

    # Return the id map
    # TODO When the hack is removed remember to remove this, too
    return id_database_map


def create_dependencies(result_dict, db_manager, id_map):
    """Fills the issue_dependencies and issue_duplicates tables in the database

    This must be run after the parse function, since that creates the
    "database_key" entry in the results dict. Without it, the results will at
    best be unreliable or errors will be thrown.

    Args:
        result_dict (dict): Contains the bug entries
        db_manager (codeface.dbmanager.DBManager): Connection to the databse
        id_map(list): contains tuples mapping the bug id to the id in the
        database

    Returns None:

    """
    for key in result_dict.keys():
        current_bug = result_dict[key]
        data = list()
        for value in current_bug["depends_on"]:
            # Retrieve the database key for any duplicates and append the list
            # with a tuple containing the current bug key and the retrieved one
            try:
                data.append((id_map[key], id_map[value]))
            except KeyError:
                # The dependent bug is not in scope of the analysis, therefore
                # ignore it
                pass
        # Make sure we have some data to insert, trying this with an empty list
        # will cause errors
        if len(data) is not 0:
            log.debug("Creating dependencies for bug {nr}".format(nr=key))
            db_manager.insert_dependencies("issue_dependencies", data)

        # Empty the data list
        del data[:]
        # Populate the issue_duplicates list
        if current_bug["dupe_of"] is not None:
            try:
                data.append((id_map[key], id_map[current_bug["dupe_of"]]))
            except KeyError:
                # The duplicate is not within scope, ignore it
                log.debug("Bug {nr} is duplicate of {dnr}, which is out of "
                          "scope".format(nr=key, dnr=current_bug["dupe_of"]))
                continue
            db_manager.insert_dependencies("issue_duplicates", data)
    return

def create_id_service_email(handle):
    """ Create an email-name combination in the following fashion:
    (FirstName LastName, <name@domain.de>)

    Args:
        handle (dict): Dictionary to handle emails with keys email, username,
            real_name

    Returns: str: The combination "Firstname Lastname, <name@domain.de>"
    """

    # TODO Find a workaround for when submitting this with an empty name field

    if handle["email"] == "nobody@mozilla.org":
        handle["real_name"] = "Nobody the test user"
    return handle["real_name"].encode('ascii', 'ignore') +\
           "<" + handle["email"] + ">"
