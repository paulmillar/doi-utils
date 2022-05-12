#!/bin/bash
#
#  This script accepts a DOI published by PSI and generates a
#  corresponding v3 metalink XML file that describes the files within
#  that dataset.
#
#  The metalink file may then be used to copy the files in that
#  dataset using a tool that understands the metalink format, such as
#  Aria2.
#

debug() {
    [ "$debug" = "1" ] && echo "$@"
}

fail() {
    echo "$@"
    exit 1
}

if [ $# -lt 1 ]; then
    echo "Usage:"
    echo
    echo "    $0 [-d] DOI"
    echo
    echo "Where:"
    echo
    echo "  -d    enable debug output"
    echo
    echo "  DOI   the dataset PID, which is:"
    echo
    echo "           a URL (e.g., https://doi.org/10.16907/d699e1f7-e822-4396-8c64-34ed405f07b7)"
    echo
    echo "           a doi URN (e.g., doi:10.16907/d699e1f7-e822-4396-8c64-34ed405f07b7)"
    echo "        or"
    echo "           an identifier (e.g., 10.16907/d699e1f7-e822-4396-8c64-34ed405f07b7)"
   exit 1
fi

if [ "$1" = "-d" ]; then
    debug=1
    shift
fi

case $1 in
    *://*)
	[ "${1#https://doi.org/}" = "$1" ] && fail "URL $1 does not start \"https://doi.org/\""
	doi=$1
	;;
    doi:*)
	doi="https://doi.org/${1#doi:}"
	;;
    *)
	doi="https://doi.org/$1"
	;;
esac

output=metalink-DOI-$(echo ${doi#https://doi.org/} | sed 's%/%-%g').xml
echo "Processing $doi"

debug Resolving landing page...
landing_page=$(curl -s -D- $doi | sed -n 's/^location: //ip' | sed 's/\r//')

debug Building JSON info URL...
info_json=https://doi.psi.ch/oaipmh/Publication/detail/$(echo ${landing_page#https://doi.psi.ch/detail/} | sed 's~/~%252F~')

debug Extracting download page URL...
download_page=$(curl -s $info_json | jq -r .downloadLink)

debug Identifying base directory...
base_dir=$(curl -s -L $download_page | sed -n 's/.*wget[^>]*> *\([^ ]*\).*/\1/p')

inventory=${base_dir}/__checksum_filename_0__
debug "Inventory URL: $inventory"

echo Writing $output

cat - >$output <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
    <published>$(date -u --iso-8601=seconds | sed 's/+00:00/Z/')</published>
EOF

curl -s $inventory | while read file hash; do
    if [ "$file" = "#" ]; then
	alg_name=$(echo $hash|sed 's/.*checksum algorithm: \([a-z0-9]*\).*/\1/')
	case "$alg_name" in
	    sha1)
		algorithm=sha-1
		;;
	    *)
		echo "Unknown algorithm \"$alg_name\" in line: $hash"
		algorithm=""
		;;
	esac
    else
	echo "    <file name=\"$file\">" >> $output
	[ "$algorithm" != "" ] && echo "        <hash type=\"$algorithm\">$hash</hash>" >> $output
	cat - >>$output <<EOF
        <url location="ch" priority="1">$base_dir/$file</url>
    </file>
EOF
    fi
done

cat - >>$output <<EOF
</metalink>
EOF
