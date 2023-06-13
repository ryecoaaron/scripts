#!/bin/bash

# this script imports portainer stacks into the openmediavault-compose plugin

if [[ $(id -u) -ne 0 ]]; then
  echo "This script must be executed as root or using sudo."
  exit 99
fi

. /usr/share/openmediavault/scripts/helper-functions

composePath="$(locate portainer_data/_data/compose | head -n1)"
echo "Portainer compose path :: ${composePath}"

ts=$(date +%s)

db="/etc/openmediavault/config.xml"
bak="/root/config_${ts}.xml"

cp -v ${db} ${bak}

cd /tmp
j=0

# loop through portainer compose files
for i in $(ls ${composePath}); do

  # create compose file path
  yml="${composePath}/$i/docker-compose.yml"

  # if compose file exists, import it
  if [ -f "${yml}" ]; then
    # increment counter
    ((j++))

    # copy compose file from portainer to temp file
    tmp=$(mktemp compose_XXXXXX.yml)
    cp -v ${yml} ${tmp}

    # if sed fails, revert to backup database and exit
    if [ $? -gt 0 ]; then
      cp -v ${bak} ${db} 
      exit 1
    fi

    # create temp body string
    tmpbody="REPLACE_ME_${j}_$(date +%s)"

    # add entry to files section in compose plugin's xml
    entry="<uuid>$(uuid)</uuid>"
    entry="${entry}<name>portainer import ${i} - ${ts}</name>"
    entry="${entry}<description>${i}</description>"
    entry="${entry}<body>${tmpbody}</body>"
    entry="${entry}<env></env>"
    omv_config_add_node_data "/config/services/compose/files" "file" "${entry}"

    # add linefeeds before and after temp body line
    sed -i "s/${tmpbody}/${tmpbody}\n/" ${db}

    # insert temp compose file from portainer after temp body line
    sed -i "/${tmpbody}/ r ${tmp}" ${db}

    # if sed fails, revert to backup database and exit
    if [ $? -gt 0 ]; then
      cp -v ${bak} ${db} 
      exit 2
    fi

    # add yaml start line
    sed -i "s/${tmpbody}/---\n${tmpbody}/" ${db}

    # remove temp body line
    sed -i "/${tmpbody}/d" ${db}

    # remove temp file
    rm -fv ${tmp}
  fi
done
