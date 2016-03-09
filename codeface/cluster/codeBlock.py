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
# Copyright 2013, Siemens AG, Mitchell Joblin <mitchell.joblin.ext@siemens.com>
# All Rights Reserved.

"""Container module for a number of code lines."""
# TODO Move module to model namespace.
# TODO There is an overlap with FileDict

from codeface.cluster.codeLine import codeLine


class codeBlock:
    """A codeBlock is a contiguous set of lines of code from a single commit.

    This object represents a continous set of of 'codeLines' from a single
    commit, including author and commiter metadata.

    Attributes:
        start (int): Starting line of the code block.
        end (int): Ending line of the code block.
        authorId (int): ID of the author of the code block.
        committerId (int): ID of the committer.
        cmtHash (str): Commit hash of the revision this block was extracted.
        groupName(int): Specifies the name of this block. This enables tracing
            the functions/features/files who are responsible for a specific
            collaboration.
        codeLines (list): List of codeLine instances.
    """
    # TODO Class name should be upper case, and must not collide with module.
    # TODO Fix capitalization on attributes.

    def __init__(self, start=None, end=None, authorId=None, committerId=None,
                 cmtHash=None, groupName=None):
        self.start = start
        self.end = end
        self.authorId = authorId
        self.committerId = committerId
        self.cmtHash = cmtHash
        self.groupName = groupName
        self.codeLines = []

    # TODO Remove Perl style getters and setters.
    def get_group_name(self):
        return self.groupName

    def get_codeLines(self):
        return self.codeLines

    def add_codeLine(self, lineNum, cmtHash, authorId, committerId):
        self.codeLines.append(
            codeLine(lineNum, cmtHash, authorId, committerId))
