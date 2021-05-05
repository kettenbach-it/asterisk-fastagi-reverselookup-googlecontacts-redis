# pylint: disable=invalid-name
"""
Load all contacts from given accounts into redis
"""
import json
import os
import sys
from datetime import datetime

import redis
from google.oauth2 import service_account
from googleapiclient.discovery import build

config = {"GOOGLE_ACCOUNTS": os.environ.get("GOOGLE_ACCOUNTS").split(","),
          "REDIS_HOST": os.environ.get("REDIS_HOST"),
          "REDIS_PORT": os.environ.get("REDIS_PORT"),
          "SERVICE_ACCOUNT_JSON": json.loads(os.environ.get("SERVICE_ACCOUNT_JSON"))}

if config["GOOGLE_ACCOUNTS"] is not None \
        and config["REDIS_HOST"] is not None \
        and config["REDIS_PORT"] is not None \
        and config["SERVICE_ACCOUNT_JSON"] is not None:

    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ") + "Got configuration from environment")
else:
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ") + "Missing config options(s). Exiting.")
    sys.exit(-1)

try:
    red = redis.Redis(host=str(config["REDIS_HOST"]), port=int(config["REDIS_PORT"]))
except (ConnectionRefusedError, redis.exceptions.ConnectionError) as exc:
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ") + ": Redis unavailabe %s" % str(exc))
    sys.exit(-1)

# Scopes must set be set in:
# https://admin.google.com/kettenbach.biz/AdminHome?chromeless=1#OGX:ManageOauthClients
SCOPES = ['https://www.googleapis.com/auth/contacts.readonly',
          'https://www.googleapis.com/auth/userinfo.profile',
          'https://www.googleapis.com/auth/user.addresses.read',
          'https://www.googleapis.com/auth/userinfo.email']
credentials = service_account.Credentials.from_service_account_info(
    config["SERVICE_ACCOUNT_JSON"], scopes=SCOPES
)

for account in config["GOOGLE_ACCOUNTS"]:
    account = account.strip()
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ") + account, end=": ")
    # Delegate domain-wide authority
    # If you have delegated domain-wide access to the service account and you want to
    # impersonate a user account, use the with_subject method of an existing
    # ServiceAccountCredentials object.
    delegated_credentials = credentials.with_subject(account)

    # Build a service object for interacting with the API
    people_service = build('people', 'v1', credentials=delegated_credentials)

    # Call the People API
    # Description of mandatory personFields:
    # https://developers.google.com/people/api/rest/v1/people/get
    request = people_service.people().connections().list(  # pylint: disable=no-member
        resourceName='people/me',
        pageSize=2000,
        personFields='names,emailAddresses,phoneNumbers,addresses,genders,organizations')
    results = request.execute()
    connections = results.get('connections', [])

    # in case pageSize is tool small, get more results:
    while True:
        if results.get('nextPageToken') is not None:
            results = people_service.people().connections().list_next(request, results).execute()  # pylint: disable=no-member
            connections.extend(results.get('connections', []))
        else:
            break

    # Iterate over results and store in Redis:
    print(len(connections))
    for person in connections:
        names = person.get('names', [])
        phoneNumbers = person.get('phoneNumbers')
        resourceName = person.get('resourceName')
        emailAddresses = person.get('emailAddresses')
        organizations = person.get('organizations')
        if names and phoneNumbers:
            for n in phoneNumbers:
                displayName = str(names[0].get('displayName'))
                givenName = str(names[0].get('givenName'))
                familyName = str(names[0].get('familyName'))
                try:
                    email = str(emailAddresses[0].get('value'))
                except TypeError:
                    email = ""
                try:
                    org = str(organizations[0].get('name'))
                except TypeError:
                    org = ""
                try:
                    ft = n['formattedType']
                except KeyError:
                    ft = ""
                try:
                    cf = n['canonicalForm']
                except KeyError:
                    cf = ""
                if cf:
                    # print(cf + ";", end="")
                    # print(resourceName + ";" , end="")
                    # print(ft + ";", end="")
                    # print(displayName+";", end="")
                    # print(familyName + ";", end="")
                    # print(givenName + ";", end="")
                    # print(org + ";", end="")
                    # print(email + ";", end="")
                    # print()

                    contact = {
                        "resourceName": resourceName,
                        "number": cf,
                        "numberType": ft,
                        "owner": account,
                        "displayName": displayName,
                        "givenName": givenName,
                        "familyName": familyName,
                        "eMail": email,
                        "organization": org
                    }

                    red.set(cf, json.dumps(contact))

print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: Done"))
