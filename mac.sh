#!/bin/bash

disksize="128G"
macdir="/srv/ssd2/mac"
vmname="${1}"
osvers="big-sur"
vmdir="${macdir}/${vmname}"

echo "Creating ${vmname} in ${vmdir}"

mkdir -p "${vmdir}"
cd "${vmdir}"

git clone --depth 1 --recursive https://github.com/kholia/OSX-KVM.git
cd OSX-KVM/

./fetch-macOS-v2.py -s ${osvers}
qemu-img convert BaseSystem.dmg -O raw BaseSystem.img
qemu-img create -f qcow2 mac_hdd_ng.qcow2 ${disksize}

xml="${vmname}.xml"
sed "s|/home/CHANGEME|${macdir}|g" macOS-libvirt-Catalina.xml > "${xml}"
xmlstarlet edit --inplace --update "/domain/name" -v "${vmname}" "${xml}"
xmlstarlet edit --inplace --update "/domain/title" -v "${vmname}" "${xml}"
xmlstarlet edit --inplace --update "/domain/uuid" -v "$(uuid)" "${xml}"
sed -i '/mac_hdd_ng.img/s/img/qcow2/' "${xml}"
sed -i '/mac address/d' "${xml}"

virsh define "${xml}"
