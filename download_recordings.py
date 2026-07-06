"""Download all call recordings from Twilio into the recordings/ folder."""
import os
import requests
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
client = Client(ACCOUNT_SID, AUTH_TOKEN)

os.makedirs("recordings", exist_ok=True)

recordings = client.recordings.list(limit=50)
if not recordings:
    print("No recordings found.")
else:
    for rec in recordings:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Recordings/{rec.sid}.mp3"
        filename = f"recordings/{rec.call_sid[:8]}_{rec.sid}.mp3"
        if os.path.exists(filename):
            print(f"Already exists: {filename}")
            continue
        resp = requests.get(url, auth=(ACCOUNT_SID, AUTH_TOKEN))
        with open(filename, "wb") as f:
            f.write(resp.content)
        print(f"Downloaded: {filename}")
