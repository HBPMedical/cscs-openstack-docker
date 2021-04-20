#!/usr/bin/env bash

CLOUDPATH="/etc/openstack"
VERBOSE=0

if [[ "$1" = "-v" ]]; then
	VERBOSE=1
fi

if [[ -n $OS_USERNAME ]]; then
	uservar=$OS_USERNAME
else
	read -p 'Username: ' uservar
fi
if [[ -n $OS_PASSWORD ]]; then
	passvar=$OS_PASSWORD
else
	read -sp 'Password: ' passvar
fi

if [[ "$OS_PROJECT_NAME" == "" ]]; then
	PRJ_FILTER="."
else
	PRJ_FILTER=" $OS_PROJECT_NAME$"
fi

if [[ "$uservar" = "" || "$passvar" = "" ]]; then
	exit 1
fi

# Prepare environment
for key in $( set | awk '{FS="="}  /^OS_/ {print $1}' ); do unset $key ; done

# Getting the unscoped token:
UNSCOPED_TOKEN="$(env -i openstack --os-cloud cscs-pollux-unscoped --os-username $uservar --os-password $passvar token issue)"
USER_ID="$(echo "$UNSCOPED_TOKEN" | grep "user_id" | awk '{print $(NF-1)}')"
UNSCOPED_TOKEN="$(echo "$UNSCOPED_TOKEN" | grep " id" | awk '{print $(NF-1)}')"

if [[ $VERBOSE -ne 0 ]]; then
	echo "Logged in user ID $uservar: $USER_ID"
fi

# Getting the project name
if [[ $VERBOSE -ne 0 ]]; then
	echo "[openstack project list]"
fi
PROJECTS="$(env -i openstack --os-cloud cscs-pollux-unscoped-token --os-token "$UNSCOPED_TOKEN" project list --format value | grep "${PRJ_FILTER}")"
if [[ $VERBOSE -ne 0 ]]; then
	echo $PROJECTS
fi

if [[ $(echo "$PROJECTS" | wc -c) -lt 5 ]]; then
	echo "CRITICAL: You don't belong to a project, having a project ID or a scoped token is not possible!"
	exit 1
elif [[ $(echo -n "$PROJECTS" | grep -c '^') -eq 1 ]]; then
	# Just one project, accepting it...
	PROJECT_ID="$(echo $PROJECTS | awk '{print $1}')"
	PROJECT_NAME="$(echo $PROJECTS | awk '{print $2}')"
	if [[ $VERBOSE -ne 0 ]]; then
		echo "Selected project $PROJECT_NAME: $PROJECT_ID"
	fi
else
	# More than one project, we need a menu
	SAVEIFS=$IFS; IFS=$'\n' read -a lines -d '' <<< "$PROJECTS"
	declare -a lines; IFS=$SAVEIFS
	PS3="Please choose an option: "
	select option in "${lines[@]}"; do
		if [[ 1 -le "$REPLY" && "$REPLY" -le ${#lines[@]} ]]; then
			PROJECT_ID="$(echo $option | awk '{print $1}')"
			PROJECT_NAME="$(echo $option | awk '{print $2}')"
			echo " * Selected project $PROJECT_NAME: $PROJECT_ID"
			break
		fi
	done
fi

if [[ "$PROJECT_ID" != "" ]]; then
	if [[ "$(grep "$PROJECT_NAME" $CLOUDPATH/clouds.yaml 2>/dev/null)" = "" ]]; then
		cat << EOF >> $CLOUDPATH/clouds.yaml
  $PROJECT_NAME:
    cloud: cscs-pollux
    auth:
      project_name: $PROJECT_NAME
      project_id: $PROJECT_ID
EOF
	fi
	if [[ "$(grep "$PROJECT_NAME" $CLOUDPATH/secure.yaml 2>/dev/null)" = "" ]]; then
		cat << EOF >> $CLOUDPATH/secure.yaml
clouds:
  $PROJECT_NAME:
    auth:
      username: $uservar
      password: $passvar
EOF
	fi
else
	exit 1
fi

cat << EOF > /usr/local/bin/openstack-cli
#!/usr/bin/env bash

openstack --os-cloud $PROJECT_NAME \$@
EOF
chmod +x /usr/local/bin/openstack-cli

if [[ -f /root/Vagrantfile ]]; then
	sed --in-place "s@^cloud_path =.*@cloud_path = '/etc/openstack'@; s@^cloud =.*@cloud = '$PROJECT_NAME'@; s@^ssh_private_key_file =.*@ssh_private_key_file = '/code/.ssh/id_rsa.myopenstackssh'@" /root/Vagrantfile
fi

if [[ $VERBOSE -ne 0 ]]; then
	echo "You can now use 'openstack --os-cloud $PROJECT_NAME'"
fi

exit 0
