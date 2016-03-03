# Copyright 2016 Cisco Systems, Inc.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

# A tiny and simple parser for the configs fetched from a cisco IOS device.
#

import re


class LineItem(object):

    def __init__(self, line):
        self.line = line
        self.text = line.strip()
        self.parent = self
        self.children = None

    def add_children(self, child):
        if self.children:
            self.children.append(child)
        else:
            self.children = [child]

    def str_list(self):
        if self.children:
            return [self.line] + [i.str_list() for i in self.children]
        else:
            return self.line

    def re_search_children(self, linespec):
        return HTParser(self.str_list()).find_objects(linespec)

    def re_match(self, regex, group=1, default=""):
        match = re.match(regex, self.line)
        return match.group(group) if match else default

    def __repr__(self):
        return "<{} '{}'>".format(self.__class__.__name__, self.text)

    def __eq__(self, other):
        return self.str_list() == other.str_list()


class HTParser(object):
    """
    A simple hierarchical text parser.

    Indents in the text are used to derive parent child
    hierarchy.
    """

    def __init__(self, cfg):
        self._indent_list = []  # Stores items as (<indent_level>,<item>)
        if isinstance(cfg, list):
            self.cfg = cfg
        elif isinstance(cfg, str):
            self.cfg = [x for x in cfg.splitlines() if x]
        else:
            raise TypeError

    def _build_indent_based_list(self):
        self._indent_list = []
        for line in self.cfg:
            match = re.match(r'([ ]*)[^! ]', line)
            if match:
                item = (len(match.group(1)), line)
                self._indent_list.append(item)

    def _find_starts(self, linespec):
        """
        Finds the start points.

        Start points matching the linespec regex are returned as list in the
        following format:
        [(item, index), (item, index).....
         """
        linespec += ".*"
        start_points = []
        for item in self._indent_list:
            match = re.search(linespec, item[1])
            if match:
                entry = (item, self._indent_list.index(item))
                start_points.append(entry)
        return start_points

    def _find_next_indent_level(self, index):
        current_indent_level = self._indent_list[index][0]
        for item in self._indent_list[(index + 1):]:
            if item[0] > current_indent_level:
                return item[0]
            else:
                return None

    def find_lines(self, linespec):
        """Find lines that match the linespec regex."""
        res = []
        linespec += ".*"
        for line in self.cfg:
            match = re.search(linespec, line)
            if match:
                res.append(match.group(0))
        return res

    def find_objects(self, linespec):
        """Find lines that match the linespec regex.

        :param linespec: regular expression of line to match
        :return: list of LineItem objects
        """
        # Note(asr1kteam): In this code we are only adding children one-level
        # deep to a given parent (linespec), as that satisfies the IOS conf
        # parsing.
        # Note(asr1kteam): Not tested with tabs in the config. Currently used
        # with IOS config where we haven't seen tabs, but may be needed for a
        # more general case.
        res = []
        self._build_indent_based_list()
        for item, index in self._find_starts(linespec):
            parent = LineItem(item[1])
            next_ident_level = self._find_next_indent_level(index)
            if next_ident_level:
                # We start iterating from the next element
                for item in self._indent_list[(index + 1):]:
                    if item[0] == next_ident_level:
                        parent.add_children(LineItem(item[1]))
                    elif item[0] > next_ident_level:  # We skip higher indent
                        continue
                    else:  # Indent level is same or lesser than item
                        break
            res.append(parent)
        return res

    def find_children(self, linespec):
        """Find lines and immediate children that match the linespec regex.

        :param linespec: regular expression of line to match
        :return: list of lines. These correspond to the lines that were
        matched and their immediate children
        """
        res = []
        for parent in self.find_objects(linespec):
            res.append(parent.line)
            res.extend([child.line for child in parent.children])
        return res
