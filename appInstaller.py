import streamlit as st
import os
import requests as rq
import json
from github import Github


# ############## CONFIGURATION ################
FLOWIDEAPPS_ORG = 'FloWide-Apps'
# KEYCLOAK_ADDRESS = 'http://keycloak'
SCRIPTHANDLER_ADDRESS = 'http://script_handler'
server = os.environ['SERVER']
# #############################################


# GET request with token and error handling
def rqgetAuth(url, token):
    rv = rq.get(url, headers={'Authorization': 'Bearer ' + token})
    if rv.status_code < 200 or rv.status_code >= 300:
        st.error('HTTP request failed!')
        st.write('*Additional information for the error:* ', rv.json())
        st.stop()
    return rv.json()


# POST request with token and error handling
def rqpostAuth(url, token, data):
    rv = rq.post(url, headers={'Authorization': 'Bearer ' + token}, data = data)
    if rv.status_code < 200 or rv.status_code >= 300:
        st.error('HTTP request failed!')
        st.write('*Additional information for the error:* ', rv.json())
        st.stop()
    return rv.json()


st.title('FloWide App Installer')
st.write(f'Current server: **{server}**')

token = st.experimental_get_query_params()['token'][0]   # get keycloak token
# userinfo_endpoint = (rq.get(f'{KEYCLOAK_ADDRESS}/auth/realms/{server}-gw/.well-known/openid-configuration').json())['userinfo_endpoint']
# userinfo = rqgetAuth(userinfo_endpoint, token)
# if 'github_token' in userinfo and 'token' in userinfo['github_token']:
#     githubToken = userinfo['github_token']['token']
# else:
#     githubToken = None

githubToken = st.text_input('GitHub token to access also private apps')
if githubToken == '':
    githubToken = None

with st.spinner('Collecting data...'):

    # initialize github object
    g = Github(githubToken)
    # get repos from organization
    org = g.get_organization(FLOWIDEAPPS_ORG)
    flowideAppsReposList = org.get_repos()
    # get tags for repos
    flowideAppsReposTags = {}
    for repo in flowideAppsReposList:
        repoTags = repo.get_tags()
        flowideAppsReposTags[repo.name] = repoTags

    # get current repos from workbench
    localReposList = rqgetAuth(f'{SCRIPTHANDLER_ADDRESS}/repo', token)

# check for already installed apps
for repo in flowideAppsReposList:
    with st.expander(repo.name, expanded=True):
        st.write(repo.html_url)
        st.write(repo.description)
        # check whether it is already installed
        installedAs = None
        for lr in localReposList.values():
            lrif = lr.get('imported_from', '')
            if lrif == repo.clone_url:
                installedAs = lr['name']
                break
        # display as installed
        if installedAs:
            st.write('**INSTALLED** as ', installedAs)
        # offer to install
        else:
            # release selection
            tags = []
            for tag in flowideAppsReposTags[repo.name]:   # extract tag names
                tags.append(tag.name)
            if tags:   # has tags
                stn = st.selectbox('Select release to install', tags, key='select1-'+str(repo.id))
                refSelect = 'refs/tags/'+stn   # save reference
            else:   # no tags
                refSelect = None
            # the installed name is not necessary to be the same as the github repo name
            installAs = st.text_input('Install as', repo.name, key='input1-'+str(repo.id))
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
            if nameOk and st.button('INSTALL', 'button1-'+str(repo.id)):
                st.write(f'Installing *{repo.name}* from github...')
                with st.spinner('in progress'):
                    postData = {
                        'name': installAs,
                        'from_url': repo.clone_url
                    }
                    if refSelect:
                        postData.update({'ref': refSelect})
                    if githubToken:
                        postData.update({'oauth_token': githubToken})
                    ret = rqpostAuth(f'{SCRIPTHANDLER_ADDRESS}/repo/import', token, json.dumps(postData))
                st.write('Done!')
