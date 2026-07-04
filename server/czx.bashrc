alias gotoworkflow='cd /data/chenzhixu/WorkFlow'
alias startworkflowclient='gotoworkflow;. fq2 ./client/deploy/start_work_flow_client.sh;goback'
alias restartworkflowclient='docker restart work_flow_client_dev'

alias startworkflowserver='gotoworkflow;. fq2 ./server/deploy/start_work_flow_server.sh;goback'
alias restartworkflowserver='docker restart work_flow_server_dev'