#!/usr/bin/env bash

DIR_CISCO=$DEST/networking-cisco

if is_service_enabled net-cisco; then

    if [[ "$1" == "source" ]]; then
        :
    fi

    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then        :
        if is_service_enabled cisco-saf; then
            source $DIR_CISCO/devstack/saf/cisco_saf
            echo "Setting up config for cisco-saf"
            setup_saf_config $DIR_CISCO
        fi

    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        cd $DIR_CISCO
        echo "Installing Networking-Cisco"
        setup_develop $DIR_CISCO

        if is_service_enabled cisco-fwaas; then
            echo "Installing neutron-fwaas"
            source $DIR_CISCO/devstack/csr1kv/cisco_fwaas
            install_cisco_fwaas
        fi

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        if is_service_enabled q-ciscorouter && is_service_enabled ciscocfgagent; then
            source $DIR_CISCO/devstack/csr1kv/cisco_neutron
            if is_service_enabled cisco-fwaas; then
                configure_cisco_fwaas
            fi
            configure_cisco_csr_router
        fi

        if is_service_enabled cisco-saf; then
            echo "Adding cisco-saf configuration parameters"
            configure_cisco_saf $DIR_CISCO
        fi

    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        if is_service_enabled q-ciscorouter && is_service_enabled ciscocfgagent; then
           if is_service_enabled cisco-fwaas; then
               start_cisco_fwaas
           fi
           start_cisco_csr_router
        fi
        if is_service_enabled cisco-saf; then
            echo "Starting cisco-saf processes"
            start_cisco_saf_processes
        fi
    fi

    if [[ "$1" == "unstack" ]]; then
        source $DIR_CISCO/devstack/csr1kv/cisco_neutron
        net_stop_neutron

        if is_service_enabled cisco-saf; then
            source $DIR_CISCO/devstack/saf/cisco_saf
            echo "Stop cisco-saf processes"
            stop_cisco_saf_processes
        fi
    fi

    if [[ "$1" == "clean" ]]; then
        :
    fi
fi
