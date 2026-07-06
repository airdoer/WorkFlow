alias gotoworkflow='cd /data/chenzhixu/WorkFlow'
alias startworkflowclient='gotoworkflow;cd client;fq2 ./deploy/start_work_flow_client.sh;goback'
alias restartworkflowclient='docker restart work_flow_client_dev'

alias startworkflowserver='gotoworkflow;cd server;fq2 ./start_work_flow_server.sh;goback'
alias restartworkflowserver='docker restart work_flow_server_container'