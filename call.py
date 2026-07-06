import os
import sys
import time
from twilio.rest import Client
from dotenv import load_dotenv
from scenarios import SCENARIOS

load_dotenv()

client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
FROM_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]
TO_NUMBER = "Voice Agent Number"
BASE_URL = os.environ["BASE_URL"]


def make_call(scenario_name):
    print(f"\nCalling [{scenario_name}]...")
    call = client.calls.create(
        to=TO_NUMBER,
        from_=FROM_NUMBER,
        url=f"{BASE_URL}/answer?scenario={scenario_name}",
        status_callback=f"{BASE_URL}/status",
        status_callback_event=["completed"],
        record=True,
    )
    print(f"  SID: {call.sid}")
    return call.sid


if __name__ == "__main__":
    scenario_names = list(SCENARIOS.keys())

    if len(sys.argv) < 2 or sys.argv[1] == "all":
        print(f"Running all {len(scenario_names)} scenarios with 90s gap between calls.")
        for i, name in enumerate(scenario_names):
            make_call(name)
            if i < len(scenario_names) - 1:
                print("  Waiting 90 seconds...")
                time.sleep(90)
        print("\nAll calls placed. Check recordings/ for transcripts.")
    elif sys.argv[1] in SCENARIOS:
        make_call(sys.argv[1])
    else:
        print(f"Unknown scenario: {sys.argv[1]}")
        print(f"Available: {', '.join(scenario_names)}")
        sys.exit(1)
