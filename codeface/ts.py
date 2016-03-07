#! /usr/bin/env python

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
# Copyright 2013 by Siemens AG, Wolfgang Mauerer <wolfgang.mauerer@siemens.com>
# All Rights Reserved.

"""Create time series from a sequence of VCS objects"""
# TODO Tear down the deprecated subsys concept, start at "__main__" placeholder
# TODO NUKE THIS MODULE. IT NO LONGER SERVES A PURPOSE!


import argparse
import os.path
import pickle

from .commit_analysis import createSeries
from .dbmanager import DBManager, tstamp_to_sql


def doAnalysis(dbfilename, destdir, revrange=None, rc_start=None):
    """Retrieves VCS object from file and creates a 'TimeSeries' from it.

    Unpickles VCS object stored in dbfilename and loads it to vcs. Then it uses
    the createSeries function to compute a 'TimeSeries' object from it.

    Notes:
        Argument destdir is never used and has no effect.
        if revrange is dead code, as sfx is never used afterwards. Except if
        it is called to provoke side-effects, in which case it is bad style.
        Also: the function name is Java-Style.

    Args:
        dbfilename (str): Binary file, containing a pickled VCS instance
        destdir (str): Output directory name, currently unused
        revrange (Optional[list]): 2-tuple of commit IDs or None.
        rc_start (Optional[str]): Commit ID within revrange or None.

    Returns:
        TimeSeries: TimeSeries instance containing the results.

    """
    pkl_file = open(dbfilename, 'rb')
    vcs = pickle.load(pkl_file)
    pkl_file.close()

    if revrange:
        sfx = "{0}-{1}".format(revrange[0], revrange[1])
    else:
        sfx = "{0}-{1}".format(vcs.rev_start, vcs.rev_end)

    res = createSeries(vcs, "__main__", revrange, rc_start)
    return res


def writeReleases(dbm, tstamps, conf):
    """Inserts all releases for the time stamps into the database.

    Args:
        dbm (DBManager): Database manager of the database to insert into.
        tstamps (list): Time stamps to be inserted.
        conf (Configuration): Codeface configuration file.
    """

    pid = dbm.getProjectID(conf["project"], conf["tagging"])

    for tstamp in tstamps:
        dbm.doExec("UPDATE release_timeline SET date=%s WHERE " +
                   "projectId=%s AND type=%s AND tag=%s",
                   (tstamp_to_sql(int(tstamp[2])), pid, tstamp[0], tstamp[1]))
    dbm.doCommit()


def dispatch_ts_analysis(resdir, conf):
    """Setup and dispatch of time series analysis.

    Extracts the knowledge necessary for the time series analysis from the
    conf and dispatches the job. The dispatch happens in two stages:
    Stage 1: Create the individual time series (and record all time
    stamps for the boundaries).
    Stage 2: Insert time stamps for all releases considered into the database.

    Notes:
        During stage 1, the time stamp information in the database is still
        incomplete, as it is written out _after_ this stage. So we must not rely
        on the content of tstamps before that is done.

    Args:
        resdir (str): Results directory.
        conf (Configuration): Codeface configuration.
    """

    dbpath = resdir
    destdir = os.path.join(dbpath, "ts")
    dbm = DBManager(conf)

    if not os.path.exists(destdir):
        os.mkdir(destdir)

    tstamps = []
    # TODO We have a ready made list of rev ranges, why isn't this used?
    for i in range(1, len(conf["revisions"])):
        dbfilename = os.path.join(dbpath,
                                  "{0}-{1}".format(conf["revisions"][i - 1],
                                                   conf["revisions"][i]),
                                  "vcs_analysis.db")

        # TODO This is a ridiculous amount of work which is entirely discarded.
        ts = doAnalysis(dbfilename, destdir,
                        revrange=[conf["revisions"][i - 1],
                                  conf["revisions"][i]],
                        rc_start=conf["rcs"][i])

        if i == 1:
            tstamps.append(
                ("release", conf["revisions"][i - 1], ts.get_start()))

        if ts.get_rc_start():
            tstamps.append(("rc", conf["rcs"][i], ts.get_rc_start()))

        tstamps.append(("release", conf["revisions"][i], ts.get_end()))

    writeReleases(dbm, tstamps, conf)

# TODO Remove this, it's deprecated!
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('resdir')
    parser.add_argument('conf_file')
    args = parser.parse_args()

    dispatch_ts_analysis(args.resdir, args.conf_file)
