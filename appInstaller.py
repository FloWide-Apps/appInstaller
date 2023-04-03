import streamlit as st
import os
import requests as rq
import json
from github import Github
from urllib.parse import parse_qs
import re

# ############## CONFIGURATION ################
FLOWIDEAPPS_ORG = 'FloWide-Apps'
KEYCLOAK_ADDRESS = 'http://keycloak'
SCRIPTHANDLER_ADDRESS = 'http://script_handler'
SERVER = os.environ['SERVER']
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
    rv = rq.post(url, headers={'Authorization': 'Bearer ' + token}, data=data)
    if rv.status_code < 200 or rv.status_code >= 300:
        st.error('HTTP request failed!')
        st.write('*Additional information for the error:* ', rv.json())
        st.stop()
    return rv.json()


def getGithubToken(keycloak_token: str):
    resp = rq.get(f"{KEYCLOAK_ADDRESS}/auth/realms/{SERVER}-gw/broker/github/token", headers={"Authorization": f"Bearer {keycloak_token}"})
    if resp.status_code != 200:
        return None
    parsed_data = parse_qs(resp.text, strict_parsing=False)
    if 'access_token' not in parsed_data:
        return None
    if len(parsed_data['access_token']) == 0:
        return None
    return parsed_data['access_token'][0]


st.title('FloWide App Installer')
st.write(f'Current server: **{SERVER}**')

token = st.experimental_get_query_params()['token'][0]   # get keycloak token
githubToken = getGithubToken(token)

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


search_param = st.text_input('Search')

# check for already installed apps
for repo in flowideAppsReposList:
    if search_param and not re.match(fr".*{search_param}.*", repo.name):
        continue

    with st.expander(repo.name, expanded=True):
        st.write(repo.html_url)
        st.write(repo.description)
        # check whether it is already installed
        installedAs = None
        for lr in localReposList.values():
            lrif = lr.get('imported_from', '')
            if lrif == repo.clone_url:
                installedAs = lr['name']
                installedAsId = lr['git_service_id']
                break
        # display as installed
        if installedAs:
            st.write('**INSTALLED** as ', installedAs)
            # check for updates
            githubTags = repo.get_tags()   # get github tags
            if githubTags.totalCount > 0:   # github tag(s) available
                localTags = rqgetAuth(f'{SCRIPTHANDLER_ADDRESS}/repo/{installedAsId}/git/tags', token)  # get local tags            
                lgtPresent = False
                for t in localTags:
                    if str(githubTags[0].commit.sha) == t['commit']:   # local tag equals with the last tag on github
                        lgtPresent = True   # last GitHub tag presents locally
                        break
                if not lgtPresent:
                    st.info('A new version is available: ' + githubTags[0].name)
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
