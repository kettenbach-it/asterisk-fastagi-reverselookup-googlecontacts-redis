# FastAGI service for reverselookup of googlecontacts in a redis database

## What it does
This software enables you to automatically download the contacts of one
or more users in [Google GSuite aka. Google Workspace](https://workspace.google.com/intl/de/)
into a redis database, which in turn can be used via a FastAGI service
within asterisk to convert the callerids of the callers into
into plaintext names, so that devices logged on to asterisk can then
display the caller's plaintext name in addition to the number of the caller
(provided that this is stored in at least one of the google accounts the system
the system uses).

If no data is found for the callerid in the contacts,
the system will

- will display the name of the city (city network) for numbers from Germany. For example, for numbers beginning with 069, "Wiesbaden".
- for international numbers, the name of the country from which the call originates (or the callerid).



## How it works
The software consists of 3 components
- a program that cyclically transfers contacts from one or more Google users to the Redis database
- a Fast-AGI service, which is used by Asterisk for reverse lookup.
- the Redis database itself

## Installation
This service was developed with the aim of running in docker.
It will also work without docker, but docker is the recommended way.

### Prerequisites
You need to log in to the Google Cloud Console, enable the [Google People API](https://developers.google.com/people)
and create a [service account](https://cloud.google.com/iam/docs/service-accounts?hl=de) and
a [JSON-key](https://cloud.google.com/iam/docs/creating-managing-service-account-keys?hl=de) for it.

Important: You must also enable the [delegation of domain-wide permission](https://developers.google.com/identity/protocols/oauth2/service-account?hl=de#delegatingauthority) to the service account.
on.

The JSON-key must be inserted in the docker-compose file with its entire content into a
environment variable. See below.

### Using docker
The latest docker-image can be found on  [DockerHub](https://hub.docker.com/r/vkettenbach//asterisk-fastagi-reverselookup-googlecontacts-redis ).

Use [docker-compose.example.yml](docker-compose.example.yml) to run your container.

Running in docker, the configuration of the service is done in envrionment variables
as shown below:

```
version: "3.7"

services:

  # This is the FastAGI Service
  asterisk-fastagi-reverselookup-googlecontacts:
    build: .
    image: vkettenbach/asterisk-fastagi-reverselookup-googlecontacts-redis:1.0.1
    container_name: asterisk-fastagi-reverselookup-googlecontacts
    restart: unless-stopped
    network_mode: host
    depends_on:
      - asterisk-fastagi-redis
    environment:
      REDIS_HOST: "localhost"  # Hostname of Redis database
      REDIS_PORT: 6379  # Port of Redis database
      HOST: "0.0.0.0"  # IP to listen to
      PORT: 4573  # Port to listen to
      TIMEOUT: 2  # Timeout

  # This is the cron job that updates the redis database 
  # daily at 8am, 2pm and 6pm
  asterisk-fastagi-reverselookup-googlecontacts-cronjob:
    image: vkettenbach/asterisk-fastagi-reverselookup-googlecontacts-redis:1.0.1
    container_name: asterisk-fastagi-reverselookup-googlecontacts-cronjob
    restart: unless-stopped
    network_mode: host
    depends_on:
      - asterisk-fastagi-redis
    command: [ "/usr/sbin/cron", "-f" , "-L",  "> /dev/stdout " ]
    environment:
      GOOGLE_ACCOUNTS: "user1@domain.com, user2@domain.com"  # Users whose contacts will be downloaded
      REDIS_HOST: "localhost"  # Hostname of Redis database
      REDIS_PORT: 6379  # Port of redis database
      # Content of the service account file you got from google:
      SERVICE_ACCOUNT_JSON: '{
                               "type": "service_account",
                               "project_id": "<myproject-id>",
                               "private_key_id": "<private-key id>",
                               "private_key": "<private key data>",
                               "client_email": "<client-email of your key>",
                               "client_id": "<client-id of your key>",
                               "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                               "token_uri": "https://oauth2.googleapis.com/token",
                               "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                               "client_x509_cert_url": "<cert-url of your key>"
                             }'

  # This is redis
  asterisk-fastagi-redis:
    image: redis
    restart: unless-stopped
    container_name: asterisk-fastagi-redis
    network_mode: host
    volumes:
      - /opt/asterisk-redis:/data
    healthcheck:
      test: [ "CMD", "redis-cli","ping" ]
      interval: 30s
      timeout: 10s
      retries: 3



```

### Not using docker

If you want to checkout the code from git an run it using python
you need to create a virtual env to run the code. The service was
developed with Python 3.9. It will probably work down to 3.7. It won't
work with Python 2.

Here is an example of how this is done - somewhat:

```
git pull https://github.com/kettenbach-it/asterisk-fastagi-reverselookup-googlecontacts-redis 
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start redis - this is not part of this tutorial
# Use googlecontacts2redis.py to load data
export GOOGLE_ACCOUNTS=user1@domain.com
export SERVICE_ACCOUNT_JSON=<json of your service account>
export REDIS_HOST=localhost
export REDIS_PORT=6379
python3 googlecontacts2redis.py
# Start AGI
export HOST=0.0.0.0
export PORT=4573
export TIMEOUT=2
python3 googlecontacts.agi.py
```

If you do not use Docker, then you must develop the corresponding
startup scripts for these components yourself.

## Usage in Asterisk
Here's an example how you can use this FastAGI service in Asterisk
(in a Macro) assuming you deployed it to the same host Asterisk is running
at. You can deploy it to any other docker host having internet access
reachable by your asterisk host - just adjust the hostname accordingly.

```
exten => s,n,AGI(agi://localhost/)
```

After this this dialplan variable "CALLERID" will be set as described above.

## References

### Source Code
Can be found on [GitHub](https://github.com/kettenbach-it//asterisk-fastagi-reverselookup-googlecontacts-redis )

### Docker Container Image
Can be found on  [DockerHub](https://hub.docker.com/r/vkettenbach//asterisk-fastagi-reverselookup-googlecontacts-redis ).

## License
GNU AGPL v3

Fore more, see LICENSE file.
