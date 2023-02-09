import streamlit as st
import os
import requests as rq
import json
from github import Github


# ############## CONFIGURATION ############### #
FLOWIDEAPPS_ORG = 'FloWide-Apps'
keycloak = 'http://keycloak'
scriptHandler = 'http://script_handler'
server = os.environ['SERVER']
# ############################################ #


# GET request with token and error handling
def rqgetAuth(url, token):
    rv = rq.get(url, headers={'Authorization': 'Bearer ' + token})
    if rv.status_code != 200:
        st.error('HTTP request failed!')
        st.write('*Additional information for the error:* ', rv.json())
        st.stop()
    return rv.json()


# POST request with token and error handling
def rqpostAuth(url, token, data):
    rv = rq.post(url, headers={'Authorization': 'Bearer ' + token}, data=data)
    if rv.status_code != 200:
        st.error('HTTP request failed!')
        st.write('*Additional information for the error:* ', rv.json())
        st.stop()
    return rv.json()


st.title('FloWide App Installer')
st.write(f'Current server: **{server}**')

st.header('Collecting data')

# get user info from keycloak
st.write('Get user info...')
token = st.experimental_get_query_params()['token'][0]   # get keycloak token
usr_ep = f'{keycloak}/auth/realms/{server}-gw/.well-known/openid-configuration'
userinfo_endpoint = (rq.get(usr_ep).json())['userinfo_endpoint']
userinfo = rqgetAuth(userinfo_endpoint, token)
if 'github_token' in userinfo and 'token' in userinfo['github_token']:
    githubToken = userinfo['github_token']['token']
else:
    githubToken = None

st.write('Get available apps from github...')
# initialize github object
g = Github(githubToken)
# get repos from organization
org = g.get_organization(FLOWIDEAPPS_ORG)
flowideAppsReposList = org.get_repos()

# get current repos from workbench
st.write('Get list of apps currently in workbench...')
localReposList = rqgetAuth(f'{scriptHandler}/repo', token)

st.header('App list')

# check for already installed apps
for repo in flowideAppsReposList:
    with st.expander(repo.name, expanded=True):
        st.write(repo.html_url)
        st.write(repo.description)
        # check whether it is already installed
        installedAs = None
        for lr in localReposList.values():
            lrif = ''
            if lr['apps_config']['metadata']:
                lrif = lr['apps_config']['metadata'].get('imported_from', '')
            if lrif == repo.clone_url:
                installedAs = lr['name']
                break
        # display as installed
        if installedAs:
            st.write('**INSTALLED** as ', installedAs)
        # offer to install
        else:
            # the installed name is not necessary to be the same
            # as the github repo name
            installAs = st.text_input('Install as', repo.name, key=-repo.id)
            # check name (already exists, invalid)
            nameOk = True
            for lr in localReposList.values():
                if lr['name'] == installAs:
                    nameOk = False
                    st.warning('An application already exists with this name!')
                    break
            if installAs == '':
                nameOk = False
            # install!
            if nameOk and st.button('INSTALL', key=repo.id):
                st.write(f'Installing *{repo.name}* from github...')
                with st.spinner('in progress'):
                    postData = {'name': installAs, 'from_url': repo.clone_url}
                    if githubToken:
                        postData.update({'oauth_token': githubToken})
                    ret = rqpostAuth(f'{scriptHandler}/repo/import', token,
                                     json.dumps(postData))
                st.write('Done!')
