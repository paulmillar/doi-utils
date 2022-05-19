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

    checksums_qname = {
        'namespace': "http://www.dcache.org/2013/webdav",
        'name': "Checksums",
    }

    xml_namespace="urn:ietf:params:xml:ns:metalink"

    def __init__(self, url):
        parsed_url = urlparse(url)
        scheme = "https" if parsed_url.scheme == "davs" else parsed_url.scheme
        if scheme != "https":
            raise Exception('Bad scheme \"%s\" (perhaps "https"?)' % scheme)
        self.start_path = parsed_url.path
        self.prefix = scheme + "://" + parsed_url.netloc
        ET.register_namespace('', self.xml_namespace)
        self.root = ET.Element("{%s}metalink" % self.xml_namespace)
        options = {
            'webdav_hostname': self.prefix,
        }
        self.client = Client(options)

    def start(self):
        self._processDir(self.start_path)

    def _processFile(self, item):
        path=item["path"]

        url = self.prefix + path
        rel_path = item["path"][1+len(self.start_path):]
        file = ET.SubElement(self.root, "file", name=rel_path);

        ET.SubElement(file, "url", location="de",priority="1").text = url
        checksums = self.client.get_property(path, self.checksums_qname);
        ET.SubElement(file, "size").text = item["size"]
        for checksum in checksums.split(","):
            (alg,value) = checksum.split("=", 1);
            if alg == "md5":
                value = base64.b64decode(value).hex()
            ET.SubElement(file, "hash", type=alg).text = value

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
        filename = self.start_path[1:].replace("/","_") + ".meta4"
        tree.write(filename, xml_declaration=True)
        print("Wrote dataset metalink: %s" % filename)


def main(argv):
    parser = argparse.ArgumentParser(description='Walk a WebDAV server, building metalink file.')
    parser.add_argument('url', metavar='URL', help='the URL of the WebDAV server')
    args = parser.parse_args()
    walker = FileWalker(args.url)
    walker.start()
    walker.printTree()

if __name__ == "__main__":
    main(sys.argv[1:])
