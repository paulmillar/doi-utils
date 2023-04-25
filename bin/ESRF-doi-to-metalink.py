#!/usr/bin/env python3
#
#  Generate metalink files for the ESRF datasets.
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

def main():
    parser = OptionParser("usage: %prog [options] DOI")
    parser.add_option("-z", action="store_true", dest="suppress_zero", default=False,
                  help="don't include zero-length files.")    
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

            #  The following URL is presented in the web pages:
            #
            #    "https://icatplus.esrf.fr/catalogue/%s/data/download?datafileIds=%s" % (sessionId, info ["id"])
            #
            #  The "icatplus.esrf.fr" server redirects to "ids.esrf.fr".
            #  While valid HTTP, this seems to cause problems for some
            #  clients.  Therefore, we avoid this redirection by using the
            #  "ids.esrf.fr" URL directly.
            #
            url="https://ids.esrf.fr/ids/getData?sessionId=%s&datafileIds=%s" % (sessionId, info ["id"])
            file = ET.SubElement(root, "file", name=info["name"])
            ET.SubElement(file, "size").text = str(info ["fileSize"])
            ET.SubElement(file, "url", location="fr",priority="1").text = url
            ET.SubElement(file, "description").text = info ["location"]

        tree = ET.ElementTree(root)
        output = "%s.meta4" % dataset_name
        tree.write(output, xml_declaration=True)
        print("Wrote dataset metalink: %s" % output)

if __name__ == "__main__":
    main()
