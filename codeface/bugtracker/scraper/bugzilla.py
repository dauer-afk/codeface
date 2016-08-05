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

"""Container module for the bugzilla bug tracker."""
import time
import json
import requests
import codeface.bugtracker.filesystem_cache as fs_cache


def init_first_url(url_queue, conf):
    """
    The query will return a dict with the single key "bugs" containing a list
    of dicts the the keys "id" and the bug IDs as values


    Args:
        conf(codeface.configuration.Configuration):
        url_queue(queue):

    Returns:

    """
    rest_query = str("?include_fields=id&product=" + conf["project_id"] +
                     "&resolution=---")
    rest_result = requests.get(rest_query)
    # Response is good, continue
    if rest_result.ok:
        rest_dict = json.load(rest_result)
        rest_list = rest_dict["bugs"]
        for item in rest_list:
            for key in item:
                url_queue.put(item[key])


def scrape(url_queue, conf, results, cachedir):
    """In this case, forego the urls, since the bug tracker offers the use of
    bug ids

    Args:
        url_queue(Queue):
        conf(codeface.configuration.Configuration):
        results(dict)

    Returns:

    """
    while not url_queue.empty():
        current_bug = url_queue.get()
        rest_query = str(conf["bugtracker_url"] + "rest/bug") + current_bug
        current_rest = requests.get(rest_query)
        current_json_dict = json.loads(current_rest)
        current_list = current_json_dict["bugs"]

        results[str(current_bug)] = current_list
        fs_cache.put_in_cache(current_bug, current_list, cachedir)

        # Time limit to prevent DoS
        time.sleep(1)

def parse(handle, db_manager, id_service):
    """

    Args:
        handle (dict):
        db_manager (codeface.dbmanager.DBManager):
        id_service (codeface.cluster.idManager.idManager):
    """
    # implement JSON logic, SQL statement
    # https://bmo.readthedocs.org/en/latest/api/core/v1/bug.html#rest-single-bug
    # TODO extend this one with an intelligent reassingement of persons
    if handle["dupe_of"] is not None:
        return

    # Exchange persons for IDs from the database
    handle["assigned_to"]  = id_service.getPersonID(handle["assigned_to"])
    handle["creator"] = id_service.getPersonID(handle["creator"])
    for addr in handle["cc"]:
        addr = id_service.getPersonID(addr)

    # Put the bug into the database
    sql_statement = "INSERT INTO issue (bugId, creationDate, modifiedDate," \
                    " url, resolution, severity, priority, createdBy," \
                    " assignedTo, projectId) VALUES (%s, %s, %s, %s, %s, %s," \
                    " %s, %s, %s, %s)"
    data = [handle, handle["creation_time"], handle["last_change_time"],
            handle["url"], handle["resolution"], handle["severity"],
            handle["priority"], handle["creator"], handle["assigned_to"],
            handle["product"]]

    db_manager.doExec(sql_statement, data)

    sql_statement = "INSERT INTO cc_list (issueId, who) VALUES (%s, %s)"
    data = None
    for addr in handle["cc"]:
        data.append((handle, addr))

    db_manager.doExec(sql_statement, data)
