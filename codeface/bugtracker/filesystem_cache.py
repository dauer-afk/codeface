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
Cache module to manage the on-disk cache scraped from the web
"""

import os
import hashlib
import pickle

# reasoning: est. 6 * 10 pow 5 entries, ext 2 has performance issues past
# 10 000 entries. 3 equl 4096 4 equl 46012. therefore either DB or second lvl


def compute_path(cachedir, current_url):
    """Compute the storage path.
    Computes the hash, slices the first three letters as subdirectory and
    and concatenates the whole as an absolute path on the system.
    Args:
        current_url:

    Returns:
        object:

    Returns: dict containing target_path and current hash

    """
    current_hash = hashlib.sha256(current_url).hexdigest()

    # Assuming hash collisions do not exist...
    return os.path.join(os.path.abspath(cachedir), current_hash[:2],
                        current_hash[2:4], current_hash[4:])


# TODO exchange Exceptions with more precise things and integrate logging

def get_url(current_url=None):
    """
    Retrieves current raw from cache using pickle
    Args:
        current_url:

    Returns:

    """

    # Check for present input
    if current_url is None:
        raise Exception

    target_path = compute_path(current_url)

    if not os.path.exists(target_path):
        return None

    target = open(target_path, 'r')

    current_raw = pickle.load(target)
    target.close()

    return current_raw


def put_in_cache(current_url, current_raw, cachedir):
    """
    Puts current raw in cache using pickle
    Args:
        current_url(str):
        current_raw(str):
        cachedir(str):

    Returns:

    """

    # Check for present input
    if current_url is None or current_raw is None or cachedir is None:
        raise Exception

    target_path = compute_path(cachedir, current_url)

    # If target directory does not exist, create it
    # since it is not threadsafe, ignore the error when creating an
    # existing dir
    if not os.path.exists(os.path.dirname(target_path)):
        try:
            os.makedirs(os.path.dirname(target_path))
        except:
            pass

    # Open file, (over-)write into it, close
    target = open(target_path, 'w')
    pickle.dump(current_raw, target)
    target.close()

    return
