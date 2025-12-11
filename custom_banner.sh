if [[ $- == *i* ]]; then
    RED='\033[0;31m'
    BOLD_RED='\033[1;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    NC='\033[0m'
    PAD="                       " 

    echo -e "${CYAN}"
    cat << "ART"
   _____                _           _   _                _____           
  |  __ \              | |         | | (_)              / ____|          
  | |__) | __ ___   __| |_   _  ___| |_ _   ___  _ __   | (___   ___ _ ____   _____ _ __ 
  |  ___/ '__/ _ \ / _` | | | |/ __| __| |/ _ \| '_ \   \___ \ / _ \ '__\ \ / / _ \ '__|
  | |   | | | (_) | (_| | |_| | (__| |_| | (_) | | | |  ____) |  __/ |   \ V /  __/ |   
  |_|   |_|  \___/ \__,_|\__,_|\___|\__|_|\___/|_| |_| |_____/ \___|_|    \_/ \___|_|   
ART
    echo -e "${NC}"

    echo -e "${PAD}${BOLD_RED}##########################################${NC}"
    echo -e "${PAD}${BOLD_RED}#                ATENÇÃO!                #${NC}"
    echo -e "${PAD}${BOLD_RED}#     ESTE É UM SERVIDOR DE PRODUÇÃO     #${NC}"
    echo -e "${PAD}${BOLD_RED}##########################################${NC}"
    echo ""
    echo -e "${PAD}${YELLOW}Ambiente crítico de alta disponibilidade.${NC}"
    echo -e "${PAD}Sem permissão? ${BOLD_RED}SAIA IMEDIATAMENTE!${NC}"
    echo -e "${PAD}Acesso monitorado e auditado."
    echo ""
    echo -e "${PAD}${CYAN}--- STATUS DO SISTEMA ---${NC}"
    echo -e "${PAD}${GREEN}Data.......:${NC} $(date '+%d/%m/%Y %H:%M:%S')"
    echo -e "${PAD}${GREEN}Tempo Ativo:${NC} $(uptime -p | sed 's/up //;s/hours/horas/;s/minutes/minutos/;s/days/dias/')"
    echo -e "${PAD}${GREEN}Carga CPU..:${NC} $(cat /proc/loadavg | awk '{print $1, $2, $3}')"
    echo -e "${PAD}${GREEN}Disco (/)..:${NC} $(df -h / | awk 'NR==2 {print $5 " usado de " $2}')"
    echo -e "${PAD}${GREEN}Sessões....:${NC} $(who | wc -l) ativa(s)"
    echo -e "${PAD}${CYAN}-------------------------${NC}"
    echo ""
fi
