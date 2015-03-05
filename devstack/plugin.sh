#!/bin/sh

DIR_CISCO=$DEST/networking-cisco

if is_service_enabled net-cisco; then

    if [[ "$1" == "source" ]]; then
        :
    fi

    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then        :
        :

    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        cd $DIR_CISCO
        echo "Installing Networking-Cisco"
        sudo python setup.py install

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        :

    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        :

    fi

    if [[ "$1" == "unstack" ]]; then
        :
    fi

    if [[ "$1" == "clean" ]]; then
        :
    fi
fi