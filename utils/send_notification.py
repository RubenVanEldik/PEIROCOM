import http
import urllib

import utils
import validate

# Initialize the Pushover client if the keys are available
user_key = utils.get_env("PUSHOVER_USER_KEY")
api_token = utils.get_env("PUSHOVER_API_TOKEN")

def send_notification(message):
    """
    Send a notification via Pushover, if a key and token are set
    """
    assert validate.is_string(message)

    # Send the message if the user key and API token are found
    if user_key and api_token:
        # Define the headers and body
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        body = urllib.parse.urlencode({"token": api_token, "user": user_key, "message": message})

        try:
            # Send the request
            pushover_connection = http.client.HTTPSConnection("api.pushover.net:443")
            pushover_connection.request("POST", "/1/messages.json", body, headers)
            pushover_connection.getresponse()
        except ConnectionError:
            print("Could not send the notification due to an connection error")
