#!/usr/bin/env python3
#
#  Generate a metalink file for a WebDAV directory.  This script also
#  supports extracting checksum information.

from webdav3.client import Client
import xml.etree.cElementTree as ET
import base64
import sys
import argparse
from urllib.parse import urlparse

class FileWalker:
    """ A class that walks a WebDAV endpoint, starting at a
    specific directory.  It building a metalink description
    of the available files.
    """

    dcache_checksums_qname = {
        'namespace': "http://www.dcache.org/2013/webdav",
        'name': "Checksums",
    }

    xml_namespace="urn:ietf:params:xml:ns:metalink"

    def __init__(self, args):
        parsed_url = urlparse(args.url)
        if parsed_url.scheme == "davs":
            parsed_url.scheme = "https"
        if parsed_url.scheme != "https":
            raise Exception('Bad scheme \"%s\" (perhaps "https"?)' % parsed_url.scheme)

        self.start_path = parsed_url.path
        self.prefix = parsed_url.scheme + "://" + parsed_url.netloc
        ET.register_namespace('', self.xml_namespace)
        self.root = ET.Element("{%s}metalink" % self.xml_namespace)
        self.client = self._build_client(parsed_url)
        self.output = args.output [0] if args.output else (self.start_path[1:].replace("/","_") + ".meta4")
        self.location = args.location [0] if args.location else None

    def _build_client(self, parsed_url):
        options = {}
        username_without_password = None
        userinfo = parsed_url.netloc.split("@", 1)
        if len(userinfo) == 1:
            options["webdav_hostname"] = parsed_url.scheme + "://" + parsed_url.netloc
        else:
            options["webdav_hostname"] = parsed_url.scheme + "://" + userinfo[1]
            credential = userinfo[0].split(":", 1)
            if len(credential) == 1:
                raise Exception('Missing \':\' in URL\'s userinfo \"%s\"' % userinfo[0])
            if not credential [1]:
                username_without_password = credential [0]
            else:
                options["webdav_login"] = credential [0]
                options["webdav_password"] = credential [1]

        client = Client(options)

        # Work around a limitation of the webdav client
        #
        # https://github.com/ezhov-evgeny/webdav-client-python-3/issues/123
        #
        if username_without_password:
            client.session.auth = (username_without_password, "")

        return client

    def start(self):
        self._processDir(self.start_path)

    def _addDcacheChecksums(self, item, file):
        checksums = self.client.get_property(item["path"], self.dcache_checksums_qname);
        if checksums:
            for checksum in checksums.split(","):
                (alg,value) = checksum.split("=", 1);
                if alg == "md5":
                    value = base64.b64decode(value).hex()
                ET.SubElement(file, "hash", type=alg).text = value

    def _processFile(self, item):
        path=item["path"]

        url = self.prefix + path
        rel_path = item["path"][1+len(self.start_path):]
        file = ET.SubElement(self.root, "file", name=rel_path);

        urlElement = ET.SubElement(file, "url", priority="1")
        urlElement.text = url
        if self.location:
            urlElement.set("location", self.location)

        ET.SubElement(file, "size").text = item["size"]
        self._addDcacheChecksums(item, file)

    def _processDir(self, dir):
        print("Processing dir " + dir)
        for item in self.client.list(dir, get_info=True):
            isDir = item["isdir"]
            if isDir:
                self._processDir(item["path"])
            else:
                self._processFile(item)

    def printTree(self):
        tree = ET.ElementTree(self.root)
        tree.write(self.output, xml_declaration=True)
        print("Wrote dataset metalink: %s" % self.output)


def main(argv):
    parser = argparse.ArgumentParser(description='Walk a WebDAV server, building metalink file.')
    parser.add_argument('url', metavar='URL', help='the URL of the WebDAV server.  This URL may contain username and password information, which will be copied into individual file URLs.')

    parser.add_argument('-o', '--output', nargs=1, metavar='FILE',
                        help="the name of the filename, which should have the '.meta4' extension.  If not specified then an auto-generated filename is used.")

    parser.add_argument('--location', nargs=1, metavar='COUNTRY',
                        help="The country within which the WebDAV server resides.  COUNTRY is an ISO 3166-1 2-alpha code.")

    args = parser.parse_args()
    walker = FileWalker(args)
    walker.start()
    walker.printTree()

if __name__ == "__main__":
    main(sys.argv[1:])
