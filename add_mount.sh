#!/bin/bash

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <mount_path> <remote_nfs>"
    exit 1
fi

path="${1}"
remote="${2}"

# Escape the mount path for use in systemd unit names
epath=$(systemd-escape --path "${path}")

# Create mount point if it does not exist
mkdir -p "${path}"

# Create the mount unit file
mfile="/etc/systemd/system/${epath}.mount"
cat > "${mfile}" << EOF
[Unit]
Description=NFS mount for ${path}
Requires=network-online.target
After=network-online.target

[Mount]
What=${remote}
Where=${path}
Type=nfs
Options=rsize=8192,wsize=8192,timeo=21,nofail

[Install]
WantedBy=multi-user.target
EOF

# Check if mount unit file creation was successful
if [ $? -ne 0 ]; then
    echo "Failed to create mount unit file."
    exit 1
fi

# Create the automount unit file
afile="/etc/systemd/system/${epath}.automount"
cat > "${afile}" << EOF
[Unit]
Description=Automount for ${path}

[Automount]
Where=${path}
TimeoutIdleSec=10

[Install]
WantedBy=multi-user.target
EOF

# Check if automount unit file creation was successful
if [ $? -ne 0 ]; then
    echo "Failed to create automount unit file."
    exit 2
fi

# Reload systemd manager configuration
systemctl daemon-reload

# Enable and start the mount unit
systemctl enable "${epath}.mount"
if [ $? -ne 0 ]; then
    echo "Failed to enable mount unit."
    exit 3
fi

systemctl start "${epath}.mount"
if [ $? -ne 0 ]; then
    echo "Failed to start mount unit."
    exit 4
fi

echo "NFS mount setup completed successfully."

exit 0
