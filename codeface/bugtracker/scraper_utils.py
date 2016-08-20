"""Collection of utilities for managing various aspects of the bugtrackersw"""

import os
from Queue import Queue


def remove_outer_list(target_dir):
    """Remove outer list from pickled objects in cache.

    Was created due to mistake in reading python

    Args:
        target_dir (str):

    Returns (bool):

    """
    target_dir = os.path.abspath(target_dir)
    number_of_files = 0
    for current_dir, sub_dirs, files in os.walk(target_dir, topdown=True,
                                                onerror=None):
        for file in files:
            number_of_files +=1
            #print "Processing file " + current_dir + "/"+ file
            """target_file = open(current_dir + "/" + file, "r+")
            current_data = pickle.load(target_file)
            target_file.seek(0)
            if type(current_data) == list:
                number_of_files += 1
                current_data = current_data[0]
                pickle.dump(current_data, target_file)
            target_file.close()
            current_data = None"""
    print "We have processed " + str(number_of_files) + " files"


def max_queue_size():
    """We are not suffering from python limitations! - made for reassurance"""
    lst = list()
    for i in range(1, 1000000):
        lst.append(i)
    print len(lst)
    que = Queue()
    for i in range(1, 1000000):
        que.put(i)
    print que.qsize()

remove_outer_list("../../cache_ff")
