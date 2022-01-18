#!/bin/bash

declare -a cmd_opts

# Make the data directory if it doesn't yet exist:
if [[ ! -d $SENDRIA_DATA_DIR ]]; then
  mkdir -p $SENDRIA_DATA_DIR
fi

### set any command line options that need setting:

if [[ -n $DB_PATH ]] && [[ $DB_PATH =~ \.sqlite$ ]]; then
  # Full path given
  cmd_opts+=("--db=${DB_PATH}")
elif [[ -n $DB_PATH ]] && [[ ! $DB_PATH =~ \.sqlite$ ]] && [[ ! $DB_PATH =~ \/$ ]]; then
  # No db file and no trailing slash
  cmd_opts+=("--db=${DB_PATH}/mail.sqlite")
elif [[ -n $DB_PATH ]] && [[ ! $DB_PATH =~ \.sqlite$ ]] && [[ $DB_PATH =~ \/$ ]]; then
  # No db file but with trailing slash
  cmd_opts+=("--db=${DB_PATH}mail.sqlite")
else
  cmd_opts+=("--db=${SENDRIA_DATA_DIR}/mail.sqlite")
fi

if [[ -n $SMTP_USER ]] && [[ -n $SMTP_PASS ]]; then
  # Both username and password given
  htpasswd -bBc ${SENDRIA_DATA_DIR}/.smtp.htpasswd $SMTP_USER $SMTP_PASS
  # echo "${SMTP_USER}:$(openssl passwd -5 ${SMTP_PASS})" >> ${SENDRIA_DATA_DIR}/.smtp.htpasswd
  cmd_opts+=("--smtp-auth=${SENDRIA_DATA_DIR}/.smtp.htpasswd")
elif [[ -z $SMTP_USER ]] && [[ -n $SMTP_PASS ]]; then
  # Only password given
  # echo "smtp-user:$(openssl passwd -5 ${SMTP_PASS})" >> ${SENDRIA_DATA_DIR}/.smtp.htpasswd
  htpasswd -bBc ${SENDRIA_DATA_DIR}/.smtp.htpasswd smtp-user $SMTP_PASS
  cmd_opts+=("--smtp-auth=${SENDRIA_DATA_DIR}/.smtp.htpasswd")
elif [[ -n $SMTP_USER ]] && [[ -z $SMTP_PASS ]]; then
  # Only username given
  echo "smtp-user:" > ${SENDRIA_DATA_DIR}/.smtp.htpasswd
  cmd_opts+=("--smtp-auth=${SENDRIA_DATA_DIR}/.smtp.htpasswd")
fi

if [[ -n $HTTP_USER ]] && [[ -n $HTTP_PASS ]]; then
  # Both username and password given
  # echo "${HTTP_USER}:$(openssl passwd -5 ${HTTP_PASS})" >> ${SENDRIA_DATA_DIR}/.http.htpasswd
  htpasswd -bBc ${SENDRIA_DATA_DIR}/.http.htpasswd $HTTP_USER $HTTP_PASS
  cmd_opts+=("--http-auth=${SENDRIA_DATA_DIR}/.http.htpasswd")
elif [[ -z $HTTP_USER ]] && [[ -n $HTTP_PASS ]]; then
  # Only password given
  # echo "admin:$(openssl passwd -5 ${HTTP_PASS})" >> ${SENDRIA_DATA_DIR}/.http.htpasswd
  htpasswd -bBc ${SENDRIA_DATA_DIR}/.http.htpasswd admin $HTTP_PASS
  cmd_opts+=("--http-auth=${SENDRIA_DATA_DIR}/.http.htpasswd")
elif [[ -n $HTTP_USER ]] && [[ -z $HTTP_PASS ]]; then
  # Only username given
  echo "admin:" > ${SENDRIA_DATA_DIR}/.http.htpasswd
  cmd_opts+=("--http-auth=${SENDRIA_DATA_DIR}/.http.htpasswd")
fi

if [[ $DEBUG =~ ^[Tt][Rr][Uu][Ee]$ ]]; then
  cmd_opts+=("-d")
fi

if [[ $NO_QUIT =~ ^[Tt][Rr][Uu][Ee]$ ]]; then
  cmd_opts+=("-n")
fi 

if [[ $NO_CLEAR =~ ^[Tt][Rr][Uu][Ee]$ ]]; then
  cmd_opts+=("-c")
fi

if [[ -n $TEMPLATE_NAME ]]; then
  cmd_opts+=("--template-header-name=$TEMPLATE_NAME")
fi

if [[ -n $TEMPLATE_URL ]]; then
  cmd_opts+=("--template-header-url=$TEMPLATE_URL")
fi


# Run the command that needs running:
unset SMTP_PASS HTTP_PASS
echo "${cmd_opts[@]}"
if [[ -n $LOG_FILE ]]; then
  sendria --foreground --smtp-ip=0.0.0.0 --http-ip=0.0.0.0 "${cmd_opts[@]}" | tee -a $LOG_FILE
else
  sendria --foreground --smtp-ip=0.0.0.0 --http-ip=0.0.0.0 "${cmd_opts[@]}"
fi
exit $?