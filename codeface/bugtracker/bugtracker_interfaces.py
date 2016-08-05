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
Interface class for cache
"""


class CacheInterface(object):

    def get_url(self, target_url):
        raise NotImplementedError
        return current_raw

    def put_in_cache(self, current_url, current_raw):
        raise NotImplementedError


class ScraperInterface(object):

    @staticmethod
    def init_url_queue(conf, url_queue):
        raise NotImplementedError

    #write a wrapper for those two

    @staticmethod
    def scrape_target(target_url, bugtracker_type, cache_type, cache_dir=None):
        raise NotImplementedError

    @staticmethod
    def parse_target(target_url, bugtracker_type, cache_type, cache_dir=None):
        raise NotImplementedError
