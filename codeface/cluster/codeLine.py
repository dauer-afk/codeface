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
"""Container module for codeLine class."""

# TODO Move module to model namespace.


class codeLine:
    """Container class for storing meta information on a single line of code.

    Attributes:
        lineNum (int): Original line number.
        cmtHash (str): Commit hash.
        authorId (int): Numeric ID of the author, as used in the DB layer.
        committerId (int): Numeric ID of the committer as used in the DB layer.
    """

    # TODO Class name should be upper case, and must not collide with module.
    # TODO Fix capitalization on attributes.

    def __init__(self, lineNum=None, cmtHash=None, authorId=None,
                 committerId=None):
        self.lineNum = lineNum
        self.cmtHash = cmtHash
        self.authorId = authorId
        self.committerId = committerId

    # TODO Remove Perl style getters and setters.
    def get_lineNum(self):
        return self.lineNum

    def set_lineNum(self, lineNum):
        self.lineNum = lineNum

    def get_cmtHash(self):
        return self.cmtHash

    def set_cmtHash(self, cmtHash):
        self.cmtHash = cmtHash

    def get_authorId(self):
        return self.authorId

    def set_authorId(self, authorId):
        self.authorId = authorId

    def get_committerId(self):
        return self.committerId

    def set_commiterId(self, committerId):
        self.committerId = committerId
