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
Generic scraper module for processing bugtrackers - also: testing purposes
"""


from random import randint
from codeface.bugtracker.bugtracker_interfaces import ScraperInterface
import time
import codeface.bugtracker.filesystem_cache as cache

class Generic(ScraperInterface):
    """
    Dummy/Test generic class for the scraper
    It does not process the URLs it is fed, instead it only
    empties the queue and reports done
    For i/o function testing, mostly
    """
    def enqueue(self):
        """
        Checks/enqueues new urls
        Returns:

        """
        # extract method to check/enqueue new urls
        pass

    # dummy function of testings
    @staticmethod
    def perform_job(url_queue=None, url_dict=None):
        """
        @type url_queue: multiprocessing.JoinableQueue
        @type url_dict: dict

        """
        if url_dict is None or url_queue is None:
            raise RuntimeError("No dict or queue available. Aborting.")

        while not url_queue.empty():
            current_url = url_queue.get()
            current_raw = cache.get_url(current_url)

            if current_raw is None:
                cache.put_in_cache("https:\\test.de", "Testing, testing")

            # container for future jobs
            additional_urls = list()

            # TODO parse line by line - in this case, only extract urls

            # Enqueue new jobs
            for new_url in additional_urls:
                if new_url not in url_dict:
                    url_queue.put(new_url)
                    url_dict[new_url] = True

            time.sleep(randint(1, 10))
            print current_url + " done, proceeding!"
            url_queue.task_done()
