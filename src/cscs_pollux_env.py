#!/usr/bin/env python3

# WARNING: this program requires the openstack python libraries installed. Please refer to https://github.com/eth-cscs/openstack/tree/master/cli for instructions.
# - Compute (Nova)
# - Image Service (Glance)
# - Object Storage (Swift)
# - Dashboard (Horizon)
# - Identity Service (Keystone)
# - Networking (Neutron)
# - Block Storage (Cinder)
# - Telemetry (Ceilometer)
# - Orchestration (Heat)
# apt install python3-openstackclient python3-glance python3-swift python3-keystone python3-neutron python3-cinder python3-ceilometer python3-heat

import sys
import os
import getpass
import json
import urllib

from keystoneauth1.identity import v3
from keystoneauth1 import session as keystone_session
from keystoneclient.v3 import client as keystone_client
from keystoneauth1.extras._saml2 import V3Saml2Password
import novaclient.client as nova_client
from novaclient.v2 import servers as nova_servers

class Pollux:
    __env = {}

    def __init__(self):
        self.__env['OS_AUTH_URL'] = os.environ['OS_AUTH_URL'] if 'OS_AUTH_URL' in os.environ else 'https://pollux.cscs.ch:13000/v3'
        self.__env['OS_IDENTITY_API_VERSION'] = os.environ['OS_IDENTITY_API_VERSION'] if 'OS_IDENTITY_API_VERSION' in os.environ else '3'
        self.__env['OS_IDENTITY_PROVIDER'] = os.environ['OS_IDENTITY_PROVIDER'] if 'OS_IDENTITY_PROVIDER' in os.environ else 'cscskc'
        self.__env['OS_IDENTITY_PROVIDER_URL'] = os.environ['OS_IDENTITY_PROVIDER_URL'] if 'OS_IDENTITY_PROVIDER_URL' in os.environ else 'https://auth.cscs.ch/auth/realms/cscs/protocol/saml/'
        self.__env['OS_PROTOCOL'] = os.environ['OS_PROTOCOL'] if 'OS_PROTOCOL' in os.environ else 'mapped'
        self.__env['OS_INTERFACE'] = os.environ['OS_INTERFACE'] if 'OS_INTERFACE' in os.environ else 'public'
        self.__env['OS_REGION_NAME'] = os.environ['OS_REGION_NAME'] if 'OS_REGION_NAME' in os.environ else 'Pollux'
        self.__env['OS_COMPUTE_API_VERSION'] = os.environ['OS_COMPUTE_API_VERSION'] if 'OS_COMPUTE_API_VERSION' in os.environ else '2.1'

    def wait_key(self):
        ''' Wait for a key press on the console and return it. '''
        result = None
        if os.name == 'nt':
            import msvcrt
            result = msvcrt.getch()
        else:
            import termios
            fd = sys.stdin.fileno()

            oldterm = termios.tcgetattr(fd)
            newattr = termios.tcgetattr(fd)
            newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
            termios.tcsetattr(fd, termios.TCSANOW, newattr)

            try:
                result = sys.stdin.read(1)
            except IOError:
                pass
            finally:
                termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)

        return result

    def get_env(self):
        return self.__env

    def connect(self):
        if 'OS_TOKEN' in os.environ:
            # We've already been authenticated. We can just set the right variables
            self.__env['OS_TOKEN'] = os.environ['OS_TOKEN']
            self.__env['OS_USERNAME'] = os.environ['OS_USERNAME']
            self.__auth = v3.Token(auth_url=self.__env['OS_AUTH_URL'], token=self.__env['OS_TOKEN'])
        else:
            ### Authenticate user:
            self.__env['OS_USERNAME'] = os.environ['OS_USERNAME'] if 'OS_USERNAME' in os.environ else input('Username: ')
            self.__pw = os.environ['OS_PASSWORD'] if 'OS_PASSWORD' in os.environ else getpass.getpass()
            self.__auth = V3Saml2Password(auth_url=self.__env['OS_AUTH_URL'], identity_provider=self.__env['OS_IDENTITY_PROVIDER'], protocol=self.__env['OS_PROTOCOL'], identity_provider_url=self.__env['OS_IDENTITY_PROVIDER_URL'], username=self.__env['OS_USERNAME'], password=self.__pw)

        self.__ks_session = keystone_session.Session(auth=self.__auth)

        print('User info:', self.__env['OS_USERNAME'], self.__ks_session.get_user_id())

    def __session_rescope(self):
        # (Re-)Scope the session
        self.__auth = v3.Token(auth_url=self.__env['OS_AUTH_URL'], token=self.__ks_session.get_token(), project_id=self.__env['OS_PROJECT_ID'])
        self.__ks_session = keystone_session.Session(auth=self.__auth)
        self.__env['OS_TOKEN'] = self.__ks_session.get_token()

    def __get_nova_client(self):
        self.__nova_client = nova_client.Client(version=self.__env['OS_COMPUTE_API_VERSION'], session=self.__ks_session, auth_url=self.__env['OS_AUTH_URL'], region_name=self.__env['OS_REGION_NAME'])
        return self.__nova_client

    def __get_server_manager(self):
        self.__server_manager = nova_servers.ServerManager(self.__get_nova_client())
        return self.__server_manager

    def select_project(self):
        if 'OS_PROJECT_ID' in os.environ:
            # The token we've got from the environment is already scoped
            self.__env['OS_PROJECT_ID'] = os.environ['OS_PROJECT_ID']
        else:
            ### List user's projects:
            self.__keystone_client = keystone_client.Client(session=self.__ks_session, interface=self.__env['OS_INTERFACE'])
            projects = self.__keystone_client.projects.list(user=self.__ks_session.get_user_id())
            if 'OS_PROJECT_NAME' in os.environ:
                for project in projects:
                    if project.name == os.environ['OS_PROJECT_NAME']:
                        self.__env['OS_PROJECT_NAME'] = os.environ['OS_PROJECT_NAME']
                        self.__env['OS_PROJECT_ID'] = project.id
                        self.__session_rescope()
            else:
                print('Available projects (enter corresponding number):')
                i = None
                while i is None:
                    i = 0
                    for project in projects:
                        i += 1
                        print('%s. %s' %(i, project.name))
                    key = self.wait_key()
                    if key.isnumeric():
                        key = int(key)
                    if not isinstance(key, int) or key < 1 or key > len(projects):
                        i = None
                self.__env['OS_PROJECT_ID'] = projects[key-1].id
                self.__session_rescope()

        print('Selected project ID: ', self.__env['OS_PROJECT_ID'])

    def __get_server_list(self):
        server_manager = self.__get_server_manager()
        server_list = server_manager.list()

        return server_list

    def get_server_status_list(self):
        errors = [{'name': 'Read-only filesystem', 'match': 'Read-only file system'}, {'name': 'IO error', 'match': 'I/O error'}]
        tail_size = 50

        servers = []
        for server in self.__get_server_list():
            server_dict = {'name': server.name, 'fail': False, 'err': None}
            #console_url = server.get_console_url('novnc')
            server_dict['console_output'] = server.get_console_output()
            lines = server_dict['console_output'].splitlines()
            i = 0
            for line in lines:
                i += 1
                if not server_dict['fail'] and i > len(lines) - tail_size - 1:
                    for error in errors:
                        if not server_dict['fail']:
                            if line.find(error['match']) != -1:
                                server_dict['fail'] = True
                                server_dict['err'] = {'error': error['name'], 'line': i, 'totlines': len(lines)}

            if len(server_dict['name']) <= 6:
                server_dict['msg_spacer'] = "\t\t\t"
            elif len(server_dict['name']) <= 14:
                server_dict['msg_spacer'] = "\t\t"
            else:
                server_dict['msg_spacer'] = "\t"

            if server_dict['err'] is None:
                server_dict['msg'] = 'OK'
            else:
                server_dict['msg'] = 'FAIL: %s (%s/%s)' %(server_dict['err']['error'], server_dict['err']['line'], server_dict['err']['totlines'])

            servers.append(server_dict)

        if len(servers) == 0:
            servers = None

        return servers
