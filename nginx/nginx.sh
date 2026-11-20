#!/usr/bin/env bash
set -e

if [ "${EUID}" -ne 0 ]; then
  echo "This script should be run as root."
  exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SERVERS_DIR="/etc/nginx/conf.d/servers"

echo "Installing Nexus configs."

if [ ! -d "${SERVERS_DIR}" ]; then
  mkdir -p "${SERVERS_DIR}"
fi

for FILE in nexus-servers.conf nexus-settings.conf; do
  if [ ! -L "${SERVERS_DIR}/${FILE}" ]; then
    ln -s "${SCRIPT_DIR}/${FILE}" "${SERVERS_DIR}/${FILE}"
  fi
done

nginx -t
systemctl reload nginx.service
systemctl status nginx.service --no-pager

echo "Configs installed."
