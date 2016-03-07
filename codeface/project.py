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
# Copyright 2013 by Siemens AG
# All Rights Reserved.

"""Module containing analysis methods.

Methods:
    loginfo: Pickleable function for multiprocesssing
    project_setup: Setup analysis form configuration file
    project_analyse: Analyse git project
    mailinglist_analyse: Analyse mailing list
"""

from logging import getLogger
from os.path import join as pathjoin, split as pathsplit, abspath

from pkg_resources import resource_filename

from .cluster.cluster import doProjectAnalysis, LinkType
from .configuration import Configuration, ConfigurationError
from .dbmanager import DBManager
from .ts import dispatch_ts_analysis
from .util import (execute_command, generate_reports, check4ctags,
                   check4cppstats, BatchJobPool, generate_analysis_windows)

log = getLogger(__name__)


def loginfo(msg):
    """Pickleable function for multiprocessing

    Args:
        msg:
    """

    log.info(msg)


def project_setup(conf, recreate):
    """Updates the project in the database with the release information given in
     the configuration.

    Returns the project ID, the database manager and the list of range ids
    for the ranges between the releases specified in the configuration.
    Set up project in database and retrieve ranges to analyse

    Args:
        conf (Configuration): Project specific configuration instance.
        recreate (bool): If true, remove the project from the database first.

    Returns:
        tuple: Objects of interest for the next phases.

        project_id (int): ID of the project in the database.

        dbm (DBManager): Instance of DBManager configured for this project.

        all_range_ids (list): List of ints, containing the ID of all ranges in
        the database which have been constructed from the revision labels found
        in the configuration.
    """

    log.info("=> Setting up project '%s'", conf["project"])
    dbm = DBManager(conf)
    new_range_ids = dbm.update_release_timeline(conf["project"],
                                                conf["tagging"],
                                                conf["revisions"], conf["rcs"],
                                                recreate_project=recreate)
    project_id = dbm.getProjectID(conf["project"], conf["tagging"])
    revs = conf["revisions"]

    rev_ids = [dbm.getRevisionID(project_id, rev) for rev in revs]
    # Create pairs of all subsequent revision IDs and fetch the corresponding
    # range IDs from the database.
    all_range_ids = [dbm.getReleaseRangeID(project_id, pair) for pair in
                     zip(rev_ids[0:], rev_ids[1:])]
    return project_id, dbm, all_range_ids


# TODO analyse and document functions then remove magic numbers and constants
# TODO discuss refactoring due to too many locals and arguments
# TODO refactor this function due to multiple issues!
# C: 69, 0: Missing function docstring (missing-docstring)
# R: 69, 0: Too many arguments (12/5) (too-many-arguments)
# R: 69, 0: Too many local variables (39/15) (too-many-locals)
# C:123, 8: Invalid variable name "s1" (invalid-name)
# C:144, 8: Invalid variable name "s2" (invalid-name)
# R: 69, 0: Too many branches (13/12) (too-many-branches)
# R: 69, 0: Too many statements (80/50) (too-many-statements
def project_analyse(resdir, gitdir, codeface_conf, project_conf,
                    no_report, loglevel, logfile, recreate, profile_r,
                    n_jobs, tagging_type, reuse_db):
    """Master function for analyses of git projects.

    Notes:
        Preparation:
            Constructs the actual configuration file from the provisioned global
            and project configuration files, and settings overridden by command
            line parameters.

            Verifies that software dependencies for the analysis type requested are
            all available.

            Writes actual configuration file out to disk.

        Stage 1 (per range):
            Performs a commit analysis on every revision range deduced from the
            configuration. The actual method of analysis varies. Primary goal
            for this stage is to provide metrics for developer interaction.

            The outputs are partially written to disk and partially to the
            database.

            See cluster.py `emitStatisticalData` to see what data is written to
            which location.

        Stage 2 (per range):
            Performs a cluster analysis on the data emitted by Stage 1.

        Stage 3 (per range, optional):
            Generates visualizations of clusters with Graphviz and LuaLatex.

        Global stage 1:
            Analysis of development activity on a per-range timescale.

            Provides metrics on code changes for each commit by various diff
            types. This data is then discarded. WTF?!!

            Writes timestamps of releases and RCs to the database.

        Global stage 2:
            TODO ???

        Global stage 3:
            TODO ???

    Args:
        resdir (str): Directory to store results in.
        mldir (str): Storage directory for source mailing list.
        codeface_conf (str): Codeface configuration file, contains database access,
            PersonID settings, Java BugExtractor settings and complexity
            analysis settings.
        project_conf (str): Project configuration file, contains project name, repo
            type, mailing list storage, mailing lists, descriptions, revisions,
            rcs and tagging.
        no_report (bool): Enable/disable report generation.
        loglevel (str):
        logfile (str):
        recreate (bool): Enable/disable recreation of
        profile_r: Specify R profile.
        n_jobs (int): Number of parallel processes.
        tagging_type (str): Specify tagging type, valid ones are:
            tag, proximity, committer2author, file, feature, feature_file
        reuse_db (bool): Toggle reuse of existing database.

    """

    pool = BatchJobPool(int(n_jobs))
    conf = Configuration.load(codeface_conf, project_conf)
    tagging = conf["tagging"]
    if tagging_type is not "default":

        if tagging_type not in LinkType.get_all_link_types():
            log.critical('Unsupported tagging mechanism specified!')
            raise ConfigurationError('Unsupported tagging mechanism.')
        # we override the configuration value explicitly by cmd argument
        if tagging is not tagging_type:
            log.warn(
                "tagging value is overwritten to %s because of --tagging",
                tagging_type)
            tagging = tagging_type
            conf["tagging"] = tagging

    project = conf["project"]
    repo = pathjoin(gitdir, conf["repo"], ".git")
    project_resdir = pathjoin(resdir, project, tagging)
    range_by_date = False

    # When revisions are not provided by the configuration file
    # generate the analysis window automatically
    if len(conf["revisions"]) < 2:
        window_size_months = 3  # Window size in months
        num_window = -1  # Number of ranges to analyse, -1 captures all ranges
        revs, rcs = generate_analysis_windows(repo, window_size_months)
        conf["revisions"] = revs[-num_window - 1:]
        conf["rcs"] = rcs[-num_window - 1:]
        range_by_date = True

    # TODO Sanity checks (ensure that git repo dir exists)
    if tagging == LinkType.proximity:
        check4ctags()
    elif tagging in (LinkType.feature, LinkType.feature_file):
        check4cppstats()

    project_id, dbm, all_range_ids = project_setup(conf, recreate)

    # Save configuration file
    conf.write()
    project_conf = conf.get_conf_file_loc()

    # Analyse new revision ranges
    for i, range_id in enumerate(all_range_ids):
        start_rev, end_rev, rc_rev = dbm.get_release_range(project_id, range_id)
        range_resdir = pathjoin(project_resdir, "{0}-{1}".
                                format(start_rev, end_rev))
        prefix = "  -> Revision range {0}..{1}: ".format(start_rev, end_rev)

        # STAGE 1: Commit analysis
        s1 = pool.add(
            doProjectAnalysis,
            (conf, start_rev, end_rev, rc_rev, range_resdir, repo,
             reuse_db, True, range_by_date),
            startmsg=prefix + "Analysing commits...",
            endmsg=prefix + "Commit analysis done."
        )

        # STAGE 2: Cluster analysis
        exe = abspath(resource_filename(__name__, "R/cluster/persons.r"))
        cwd, _ = pathsplit(exe)
        cmd = []
        cmd.append(exe)
        cmd.extend(("--loglevel", loglevel))
        if logfile:
            cmd.extend(("--logfile", "{}.R.r{}".format(logfile, i)))
        # TODO Why is codeface_conf passed? It has been merged into project_conf
        cmd.extend(("-c", codeface_conf))
        cmd.extend(("-p", project_conf))
        cmd.append(range_resdir)
        cmd.append(str(range_id))

        s2 = pool.add(
            execute_command,
            (cmd,),
            {"direct_io": True, "cwd": cwd},
            deps=[s1],
            startmsg=prefix + "Detecting clusters...",
            endmsg=prefix + "Detecting clusters done."
        )

        # STAGE 3: Generate cluster graphs
        if not no_report:
            pool.add(
                generate_reports,
                (start_rev, end_rev, range_resdir),
                deps=[s2],
                startmsg=prefix + "Generating reports...",
                endmsg=prefix + "Report generation done."
            )

    # Wait until all batch jobs are finished
    pool.join()

    # Global stage 1: Time series generation
    # TODO This stage has no functionality left apart from writing release
    # timestamps to the database...
    log.info("=> Preparing time series data")
    dispatch_ts_analysis(project_resdir, conf)

    # Global stage 2: Complexity analysis
    # NOTE: We rely on proper timestamps, so we can only run after time series
    # generation
    # TODO That previous note is completely outdated and miss leading.
    log.info("=> Performing complexity analysis")
    for i, range_id in enumerate(all_range_ids):
        log.info("  -> Analysing range '%s'", range_id)
        exe = abspath(resource_filename(__name__, "R/complexity.r"))
        cwd, _ = pathsplit(exe)
        cmd = [exe]
        if logfile:
            cmd.extend(("--logfile", "{}.R.complexity.{}".format(logfile, i)))
        cmd.extend(("--loglevel", loglevel))
        cmd.extend(("-c", codeface_conf))
        cmd.extend(("-p", project_conf))
        cmd.extend(("-j", str(n_jobs)))
        cmd.append(repo)
        cmd.append(str(range_id))
        execute_command(cmd, direct_io=True, cwd=cwd)

    # Global stage 3: Time series analysis
    log.info("=> Analysing time series")
    exe = abspath(resource_filename(__name__, "R/analyse_ts.r"))
    cwd, _ = pathsplit(exe)
    cmd = [exe]
    if profile_r:
        cmd.append("--profile")
    if logfile:
        cmd.extend(("--logfile", "{}.R.ts".format(logfile)))
    cmd.extend(("--loglevel", loglevel))
    cmd.extend(("-c", codeface_conf))
    cmd.extend(("-p", project_conf))
    cmd.extend(("-j", str(n_jobs)))
    cmd.append(project_resdir)
    execute_command(cmd, direct_io=True, cwd=cwd)
    log.info("=> Codeface run complete!")


# TODO sanity check mailing lists parameter
# TODO refactor due to multiple issues
# C:217, 0: Missing function docstring (missing-docstring)
# R:217, 0: Too many arguments (8/5) (too-many-arguments)
# R:217, 0: Too many local variables (20/15) (too-many-locals)
# W:241,20: Using possibly undefined loop variable 'ml' (undefined-loop-variable
# W:246,20: Using possibly undefined loop variable 'ml' (undefined-loop-variable
# C:250,11: Invalid variable name "ml" (invalid-name)


def mailinglist_analyse(resdir, mldir, codeface_conf, project_conf, loglevel,
                        logfile, jobs, mailinglists):
    """Analyse a mailing list.

    Args:
        resdir: Directory to store results in.
        mldir: Storage directory for source mailing list.
        codeface_conf: Codeface configuration file, contains database access,
            PersonID settings, Java BugExtractor settings and complexity
            analysis settings.
        project_conf: Project configuration file, contains project name, repo
            type, mailing list storage, mailing lists, descriptions, revisions,
            rcs and tagging.
        loglevel: Amount of logging done.
        logfile:
        jobs: Maximum parallel processes to work with.
        mailinglists: Mailing lists to check.

    """

    conf = Configuration.load(codeface_conf, project_conf)
    ml_resdir = pathjoin(resdir, conf["project"], "ml")

    exe = abspath(resource_filename(__name__, "R/ml/batch.r"))
    cwd, _ = pathsplit(exe)
    cmd = []
    cmd.extend(("--loglevel", loglevel))
    cmd.extend(("-c", codeface_conf))
    cmd.extend(("-p", project_conf))
    cmd.extend(("-j", str(jobs)))
    cmd.append(ml_resdir)
    cmd.append(mldir)
    if not mailinglists:
        mailinglist_conf = conf["mailinglists"]
    else:
        mailinglist_conf = []
        for mln in mailinglists:
            # TODO check ml/mln confusion and disambiguate! should be mln (prob)
            match = [ml for ml in conf["mailinglists"] if ml["name"] == mln]
            if not match:
                log.fatal(
                    "Mailinglist '%s' not listed in configuration file!",
                    ml)
                raise Exception("Unknown mailing list")
            if len(match) > 1:
                log.fatal(
                    "Mailinglist '%s' specified twice in configuration file!",
                    ml)
                raise Exception("Invalid config file")
            mailinglist_conf.append(match[0])

    for i, ml in enumerate(mailinglist_conf):
        log.info("=> Analysing mailing list '%s' of type '%s'",
                 ml["name"],
                 ml["type"])
        logargs = []
        if logfile:
            logargs = ["--logfile", "{}.R.ml.{}".format(logfile, i)]
        execute_command([exe] + logargs + cmd + [ml["name"]],
                        direct_io=True, cwd=cwd)
    log.info("=> Codeface mailing list analysis complete!")
