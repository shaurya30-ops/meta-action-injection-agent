import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "app", "backend", ".env"))

account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")

if not account_sid or not auth_token:
    print("Error: TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN is missing in your .env!")
    exit(1)

# The Twilio number you bought (matches your TwiML Bin / inbound-trunk)
twilio_number = "+17753695318"  

# Your personal mobile number (matches the one you put in seed_crm.py)
my_personal_number = "+918529152168"

# Your LiveKit SIP domain based on the LIVEKIT_URL
livekit_sip_domain = "voicebot-9ekg9cr4.sip.livekit.cloud"

# When Twilio calls you and you pick up, Twilio will interpret this TwiML
# and forward the call into your LiveKit SIP Trunk using your SIP credentials.
twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial callerId="{my_personal_number}">
    <Sip username="marg-aakriti" password="240ctober2000">
      sip:{twilio_number}@{livekit_sip_domain};transport=tcp
    </Sip>
  </Dial>
</Response>"""

print(f"Making outbound bridging call from {twilio_number} to {my_personal_number}...")

url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
data = {
    "To": my_personal_number,
    "From": twilio_number,
    "Twiml": twiml
}

response = requests.post(url, auth=(account_sid, auth_token), data=data)

if response.status_code in (200, 201):
    call_data = response.json()
    print(f"✅ Call initiated successfully! Phone is ringing...")
    print(f"Call SID: {call_data.get('sid')}")
else:
    print(f"❌ Call failed: {response.status_code}")
    print(response.text)
