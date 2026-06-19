#!/bin/bash

rm -rf *.deb

version=$(/bin/cat version)
maintainer="Nomad Digital"
name="nd-obn-template-dostoneu-nv4"
url="http://nomad-digital.com"
description="Nomad Digital OBN Templates for Dosto Neu train type nv4"
vendor="Nomad Digital"

fpm -s dir \
    -t deb \
    -f \
    -n "${name}" \
    -v "${version}" \
    -a all \
    -m "${maintainer}" \
    --deb-no-default-config-files \
    --url "${url}" \
    --description "${description}" \
    --vendor "${vendor}" \
    --provides "${name}" \
    src/=/

