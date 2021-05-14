# pylint: disable=line-too-long,duplicate-code
"""
Fast AGI service to lookup callerids in a redis database with googlecontacts
"""
import csv
import json
import os
import socketserver
import sys
from datetime import datetime

import phonenumbers
import redis
from asterisk.agi import AGI

config = {"REDIS_HOST": os.environ.get("REDIS_HOST"),
          "REDIS_PORT": os.environ.get("REDIS_PORT"),
          "HOST": os.environ.get("HOST"),
          "PORT": os.environ.get("PORT"),
          "TIMEOUT": os.environ.get("TIMEOUT")}

if config["REDIS_HOST"] is not None \
        and config["REDIS_PORT"] is not None \
        and config["HOST"] is not None \
        and config["PORT"] is not None \
        and config["TIMEOUT"] is not None:

    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ") + "Got configuration from environment")
else:
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ") + "Missing config options(s). Exiting.")
    sys.exit(-1)

try:
    red = redis.Redis(host=str(config["REDIS_HOST"]), port=int(config["REDIS_PORT"]))
except (ConnectionRefusedError, redis.exceptions.ConnectionError) as exc:
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ") + ": Redis unavailabe %s" % str(exc))
    sys.exit(-1)


class FastAGI(socketserver.StreamRequestHandler):
    """
    FastAGI request handler for socketserver
    """
    # Close connections not finished in 5seconds.
    timeout = int(config["TIMEOUT"])

    def handle(self):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        try:
            agi = AGI(stdin=self.rfile, stdout=self.wfile, stderr=sys.stderr)

            number = phonenumbers.parse(agi.env["agi_callerid"], "DE")
            number_formatted = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
            number_nat = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.NATIONAL)
            nat_prefix = number_nat[:2]
            nat_vorwahl = number_nat.split(' ')[0]
            if number.country_code != 49:  # pylint: disable=simplifiable-if-statement
                is_international = True
            else:
                is_international = False
            new_callerid = number_nat.replace(" ", "")

            # If contact is found in redis
            if red.get(number_formatted) is not None:
                contact = json.loads(red.get(number_formatted))
                org = ""
                try:
                    org = " - Firma: " + contact["organization"]
                except KeyError:
                    pass

                new_callerid = contact["displayName"] + " (" + contact["numberType"] + ") (" + \
                               contact["eMail"] + org + ") <" + number_nat.replace(" ", "") + ">"

            # Else use ONB
            else:
                path = os.path.dirname(os.path.realpath(__file__))
                if is_international:
                    with open(path + '/ONB/internationale-telefonvorwahlen.csv', newline='') as csvfile:
                        reader = csv.reader(csvfile, delimiter=';')
                        for row in reader:
                            if row[1] == "00" + str(number.country_code):
                                new_callerid = row[0] + " <" + number_nat.replace("+", "00") + ">"
                else:
                    if nat_prefix == "01":
                        new_callerid = "Mobilfunk Deutschland <" + number_nat.replace(" ", "") + ">"
                    else:
                        with open(path + '/ONB/' + nat_prefix, newline='') as csvfile:
                            reader = csv.reader(csvfile, delimiter=';')
                            for row in reader:
                                if row[0] == nat_vorwahl:
                                    new_callerid = row[1] + " <" + number_nat.replace(" ", "") + ">"

            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ") + new_callerid)
            self.wfile.write(b"SET CALLERID \"%s\"" % new_callerid.encode())
            self.wfile.flush()


        except TypeError as exception:
            sys.stderr.write('Unable to connect to agi://{} {}\n'.
                             format(self.client_address[0], str(exception)))
        except socketserver.socket.timeout as exception:
            sys.stderr.write('Timeout receiving data from {}\n'.
                             format(self.client_address))
        except socketserver.socket.error as exception:
            sys.stderr.write('Could not open the socket. '
                             'Is someting else listening on this port?\n')
        except Exception as exception:  # pylint: disable=broad-except
            sys.stderr.write('An unknown error: {}\n'.
                             format(str(exception)))


if __name__ == "__main__":
    # Create socketServer
    server = socketserver.ForkingTCPServer((config["HOST"], int(config["PORT"])), FastAGI)
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ") + "Starting FastAGI server on " + config["HOST"] + ":" + str(
        config["PORT"]))

    # Keep server running until CTRL-C is pressed.
    server.serve_forever()
