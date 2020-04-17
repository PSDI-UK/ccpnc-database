from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re
import requests
from requests.exceptions import ConnectionError


class NoOrcidTokens(Exception):
    # Raised only when login was made impossible by connection errors
    # or other issues
    pass


class OrcidError(Exception):
    pass


class OrcidConnection(object):
    """ Provides an interface to connect with
    ORCID, given the relevant app data."""

    def __init__(self, details, session=None,
                 login_url='https://orcid.org/',
                 api_url='https://pub.orcid.org/v2.0/'):

        if session is None:
            # Use the global one
            from flask import session

        self._session = session
        self._details = details
        self._login_url = login_url
        self._api_url = api_url

    def request_tokens(self, code):
        # Get tokens from ORCID given a request code
        headers = {'Accept': 'application/json'}
        payload = dict(self._details)
        payload.update({
            'grant_type': 'authorization_code',
            'code': code,
        })

        try:
            r = requests.post(self._login_url + 'oauth/token',
                              data=payload, headers=headers)
        except ConnectionError:
            raise NoOrcidTokens('Connection to oauth/token failed')

        # Save them (if no error has occurred)
        rjson = r.json()
        if 'error' not in rjson:
            self._session.permanent = True
            self._session['login_details'] = rjson
        else:
            raise NoOrcidTokens('Connection to oauth/token returned error: ' +
                                rjson['error'])

    def get_tokens(self, code=None):
        # Retrieve existing tokens, or ask for new ones
        if code is not None:
            self.request_tokens(code)

        tk = self._session.get('login_details', None)

        if tk is None:
            raise NoOrcidTokens('No login details found')

        return tk

    def delete_tokens(self):
        session.pop('login_details', None)

    def authenticate(self, client_details):
        # Check client details vs. internally stored tokens

        tk = self.get_tokens()

        try:
            auth = True
            for k in ('orcid', 'access_token'):
                auth = auth and (client_details[k] == tk[k])
        except KeyError:
            raise ValueError('Incomplete client details')

        return auth

    def request_info(self, client_details):

        # Start by authenticating
        auth = self.authenticate(client_details)
        if not auth:
            raise OrcidError('Could not authenticate')

        tk = self.get_tokens()

        # Prepare a get request
        headers = {
            'Accept': 'application/json',
            'Authorization type': 'Bearer',
            'Access token': tk['access_token']
        }
        r = requests.get(self._api_url + tk['orcid'] + '/record',
                         headers=headers)

        try:
            rdata = r.json()
        except AttributeError:
            raise OrcidError('Error: could not retrieve ORCID info')
        if 'error-code' in rdata:
            raise OrcidError(rdata['developer-message'])

        return rdata


class FakeOrcidConnection(OrcidConnection):

    """ Provides a fake interface imitating ORCID, for debugging purposes."""

    def __init__(self):
        self._session = {}

    def request_tokens(self, code):

        if code != '123456':
            raise NoOrcidTokens('Invalid fake code! '
                                'The right fake code is 123456')

        fake_details = {
            'name': 'Johnny B. Goode',
            'access_token': 'XXX',
            'orcid': '0000-0000-0000-0000',
            'scope': '/authenticate'
        }

        self._session['login_details'] = fake_details

        return fake_details

    def request_info(self, client_details):

        self.authenticate(client_details)

        tk = self.get_tokens()

        return {'orcid-identifier': {
                'path': '0000-0000-0000-0000',
                'host': 'none',
                'uri': '0000-0000-0000-0000'
                }
                }