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

"""Cache module to manage the on-disk cache"""

import os
import hashlib
import pickle

from logging import getLogger

log = getLogger(__name__)
# reasoning: est. 6 * 10 pow 5 entries, ext 2 has performance issues past
# 10 000 entries. 3 equl 4096 4 equl 46012. therefore either DB or second lvl


def compute_path(cachedir, current_url):
    """Compute the storage path.
    Computes the hash, slices the first two letters as directory, the second
    two as a subdirectory and uses the whole as an absolute path on the system.

    Args:
        cachedir(str): absolute path to the cache directory
        current_url(str): Unique identifier for the current bug

    Returns:
        str: Absolute path to the stored file
    """
    current_hash = str(hashlib.sha256(current_url).hexdigest())

    # Assuming hash collisions do not exist...
    return os.path.join(os.path.abspath(cachedir), current_hash[:2],
                        current_hash[2:4], current_hash[4:])


def get_from_cache(current_url, cachedir):
    """Retrieves current raw bug data from cache using pickle
    Args:
        current_url(str): Identifier for the bug to be retrieved
        cachedir(str): Absolute path of the filesystem cache

    Returns:
        object: Unpickled bug data from storage.
    """

    # Check for present input
    if current_url is None:
        raise ValueError("Retrieve function was called without target")

    target_path = compute_path(cachedir, current_url)
    # Retrieve data
    log.debug("Opening file {file}".format(file=target_path))
    target = open(target_path, 'r')
    current_raw = pickle.load(target)
    target.close()

    return current_raw


def put_in_cache(current_url, current_raw, cachedir):
    """Puts current raw bug data in cache on file using pickle

    Args:
        current_url(str): Identifier for the bug to be retrieved
        current_raw(str): The raw bug data to be put in the cache
        cachedir(str): The absolute file path of the filesystem cache

    """

    # Check for present input
    if current_url is None or current_raw is None or cachedir is None:
        raise ValueError("All method arguments must be set")

    target_path = compute_path(cachedir, current_url)
    log.debug("Storing {url} in {path}".format(url=str(current_url),
                                               path=target_path))

    # If target directory does not exist, create it
    # Since creating a directory is not threadsafe, ignore the error when
    # creating an existing dir (as it is only an information message)
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
