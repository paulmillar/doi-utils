#!/usr/bin/env python3
#
#  Generate a metalink file for an ESRF dataset.
#
#  This script was updated from original one to generate metalink files for the multiple ESRF datasets
#  by watching how the ESRF web-browser/
#  JavaScript behaves.  However, the ICAT+ API (on which it depends)
#  is also documented here:
#
#      https://icatplus.esrf.fr/api-docs/
#

import requests
import sys
import json
import xml.etree.cElementTree as ET
from optparse import OptionParser

def safe_filename(f):
    while bool(f) and f[0] == '/':
        f = f[1:]
    return f

def main():
    parser = OptionParser("usage: %prog [options] DOI")
    parser.add_option("-z", action="store_true", dest="suppress_zero", default=False,
                  help="don't include zero-length files.")
    parser.add_option("-s", action="store_true", dest="suppress_size", default=False,
                  help="don't include file size.  See https://github.com/aria2/aria2/issues/2051")
    parser.add_option("-f", action="store_true", dest="follow_redirection", default=False,
                  help="resolve download URLs by following any redirections.")
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    if (not args[0].startswith("doi:")):
        print("DOI must start with \"doi:\" for example doi:10.15151/ESRF-DC-818569841")
        sys.exit(1)

    doi = args[0] [4:]

    xml_namespace="urn:ietf:params:xml:ns:metalink"
    ET.register_namespace('', xml_namespace)
    root = ET.Element("{%s}metalink" % xml_namespace)

    print("Processing DOI %s" % doi)

    # doi_url="https://doi.org/%s" % doi
    # r = requests.get(doi_url, allow_redirects=False)
    # landing_page = r.headers["location"]
    # print("landing page: %s" % landing_page)

    # Get a session
    r = requests.post("https://icatplus.esrf.fr/session", json={"password": "reader", "plugin": "db", "username": "reader"})
    r.raise_for_status()
    sessionId = r.json()["sessionId"]

    # Query dataset information about the DOI
    r = requests.get("https://icatplus.esrf.fr/doi/%s/datasets?sessionId=%s" % (doi, sessionId))
    r.raise_for_status()
    doi_info = r.json()

    if len(doi_info) == 0:
        print("No datasets found for DOI %s" % doi)
        sys.exit(1)

    for dataset in doi_info:
        dataset_id = dataset["id"]
        dataset_name = dataset["name"]

        r = requests.get("https://icatplus.esrf.fr/catalogue/%s/dataset/id/%s/datafile" % (sessionId, dataset_id))
        r.raise_for_status()

        for file in r.json():
            info = file["Datafile"]
            if info ["fileSize"] == 0 and options.suppress_zero:
                continue

            download_url="https://icatplus.esrf.fr/ids/%s/data/download?datafileIds=%s" % (sessionId, info ["id"])

            #  If request, resolve any redirections and record the resulting URL.
            if options.follow_redirection:
                r = requests.head(download_url, allow_redirects=True)
                download_url = r.url

            file = ET.SubElement(root, "file", name=safe_filename(info["name"]))
            if not options.suppress_size:
                ET.SubElement(file, "size").text = str(info ["fileSize"])
            ET.SubElement(file, "url", location="fr",priority="1").text = download_url
            ET.SubElement(file, "description").text = info ["location"]

        tree = ET.ElementTree(root)
        output = "%s.meta4" % dataset_name
        tree.write(output, xml_declaration=True)
        print("Wrote dataset metalink: %s" % output)

if __name__ == "__main__":
    main()
