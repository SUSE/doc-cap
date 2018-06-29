#!/usr/bin/env python3
#
# Converts YAML file into DocBook5
#
# Requirements:
#  * python3-ruamel.yaml
#  * python3-lxml
#
# Author
#  2018, Thomas Schraitle

__version__ = "0.1.0"
__author__ = "Thomas Schraitle <toms AT suse DOT de>"
__doc__ = "Converts YAML file into DocBook5"

import argparse
import sys
from contextlib import contextmanager

try:
    import ruamel.yaml
except ImportError:
    print("ERROR: Missing module ruamel.yaml\n"
          "Install it with:\n"
          " sudo zypper in python3-ruamel.yaml",
          file=sys.stderr)
    sys.exit(1)

try:
    from lxml import etree
    from lxml.builder import ElementMaker
except ImportError:
    print("ERROR: Missing module lxml\n"
          "Install it with:\n"
          " sudo zypper in python3-lxml",
          file=sys.stderr)
    sys.exit(2)

#print("Using ruamel.yaml v%s" % ruamel.yaml._package_data.get('__version__'))
#print("Using lxml v%s" % etree.__version__)

TEST_STR="""---
env:
  # List of domains (including scheme) from which Cross-Origin requests will be
  # accepted, a * can be used as a wildcard for any part of a domain.
  ALLOWED_CORS_DOMAINS: "[]"

  # Allow users to change the value of the app-level allow_ssh attribute.
  ALLOW_APP_SSH_ACCESS: "true"

  # The set of CAT test suites to run. If not specified it
  # falls back to a hardwired set of suites.
  CATS_SUITES: ~

sizing:
  # Flag to activate high-availability mode
  HA: false
"""

DBNS='http://docbook.org/ns/docbook'
XML='http://www.w3.org/XML/1998/namespace'
XMLID='{%s}id' % XML

E = ElementMaker(namespace=DBNS, nsmap={None: DBNS})

@contextmanager
def variablelist(root):
    """Context manager to create DocBook5 <variablelist>
       element and append it to root afterwards it's filled

    :param root: the root element to append the variablelist
    :type root: :class:`etree.Element`
    """
    node = E.variablelist()
    # node.attrib['version'] = '5.1'
    #if parser is None:
    #    parser = etree.XMLParser(ns_clean=True)
    # tree = etree.ElementTree(node, parser=parser)
    yield node
    root.append(node)


@contextmanager
def varlistentry(node):
    """Context manager to create  DocBook5 <varlistentry>

    :param node: the root element to append the varlistentry
    :type node: :class:`etree.Element`
    """
    vle = E.varlistentry()
    yield vle
    node.append(vle)


def parsecli(cliargs=None):
    """Parse CLI with :class:`argparse.ArgumentParser` and return parsed result

    :param list cliargs: Arguments to parse or None (=use sys.argv)
    :return: parsed CLI result
    :rtype: :class:`argparse.Namespace`
    """
    parser = argparse.ArgumentParser(description=__doc__,
                                     epilog="Version %s written by %s " % (__version__, __author__)
                                     )
    parser.add_argument('--version',
                        action='version',
                        version='%(prog)s ' + __version__
                        )
    parser.add_argument('-o', '--output',
                        dest='output',
                        help='save DocBook XML file to the given path',
                        )
    parser.add_argument('-r', '--rootid',
                        help='set xml:id value for root element',
                        )
    parser.add_argument('-s', '--skip-section',
                        metavar="SECTION",
                        action='append',
                        default=[],
                        help=("Skip a single YAML section "
                              "(can be used multiple times to "
                              "skip more sections)"),
                        )
    parser.add_argument('yamlfile',
                        metavar="YAMLFILE",
                        help="the YAML file to convert to DocBook 5",
                        )
    args = parser.parse_args(args=cliargs)
    return parser, args


def comments(node):
    """Searches for comments and returns the comment string

    :param node: the root element to append the varlistentry
    :type node: :class:`etree.Element`
    :return: comment as string
    """
    # We need to advance to the next entry in the list
    # as the first entry in .ca.comment is usuall(?) None
    comnodes = iter(node)
    if next(comnodes) is not None:
        comnodes = node
    com = []
    for c in comnodes:
        if c is None:
            continue
        if isinstance(c, ruamel.yaml.tokens.CommentToken):
            if not c.value.strip():
                com.append(c.value.strip())
            continue

        # Get all comments, but remove any '#' character
        for x in c:
            # Skip any strings with '\n' only
            if not x.value.strip():
                continue
            if x.value.startswith('#'):
                start = 1
            else:
                start = 0
            com.append(x.value[start:])
    return com


def convert2db(args):
    """Convert YAML to DocBook5

    :param args: Parsed argument, returned from :func:`parsecli()`
    :type args: :class:`argparse.Namespace`
    :return: element with subelements
    """

    yaml = ruamel.yaml.YAML()
    data = yaml.load(open(args.yamlfile, 'r'))
    #data = yaml.load(TEST_STR)

    root = E.appendix(E.title("YAML Configuration"))
    root.attrib.update({'version': '5.1'})
    if args.rootid:
        root.attrib.update({XMLID: args.rootid})

    # First investigate all sections and turn them into <variablelist>s
    for sec in data.keys():
        if sec in args.skip_section:
            print("** Skipping section %s" % sec)
            continue
        print("** Section: %s" % sec)
        with variablelist(root) as vl, varlistentry(vl) as node:
            vl.append(E.title(sec))

            for key in data[sec].keys():
                print("  Key:", key)
                term = E.term()
                varname = E.varname(key)
                varname.tail = ' = '
                literal = E.literal(str(data[sec][key]))
                term.append(varname)
                term.append(literal)

                # First try the *direct* comment, if it cannot
                # be find, try the section comment
                trycom = data[sec].ca.items.get(key)
                if trycom is None:
                    com = comments(data[sec].ca.comment)
                else:
                    com = comments(trycom)
                para = E.listitem(E.para("\n".join(com)))
                node.append(term)
                node.append(para)

    return root


def main():
    """Main entry point

    :return: success (=0) or not (!=0)
    :rtype: int
    """
    parser, args = parsecli()
    print(args)
    # return 1
    root = convert2db(args)
    parser = etree.XMLParser(ns_clean=True)
    tree = etree.ElementTree(root, parser=parser)
    if args.output:
        tree.write(args.output, encoding="unicode", pretty_print=True)
        print("Written DocBook 5 file to %r" % args.output)
    else:
        print(etree.tostring(root, encoding="unicode", pretty_print=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
