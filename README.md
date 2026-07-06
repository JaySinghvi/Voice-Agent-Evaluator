# Voice Agent Evaluator

An automated voice bot that calls any AI phone agent, simulates realistic patient/customer scenarios, records full conversations, transcribes them, and generates a bug report — all automatically.

Use this to stress-test, QA, and find issues in any production voice AI agent before your users do.

## What It Does

1. Places an outbound call to your target voice agent via Twilio
2. Simulates a realistic caller persona (patient, customer, etc.) using Claude AI
3. Listens to the agent's responses via Twilio's built-in speech recognition
4. Replies naturally using OpenAI TTS (`nova` voice) — sounds like a real person
5. Saves a full transcript of both sides of the conversation after every turn
6. When the call ends, runs the transcript through Claude to automatically identify bugs and quality issues
7. Appends findings to a single `bug_report.md` file

## Architecture

```
call.py  →  Twilio dials target number
                ↓
         Twilio hits /answer (Flask)
                ↓
         <Gather> listens for agent speech
                ↓
         Agent speaks → Twilio transcribes
                ↓
         Twilio hits /gather (Flask)
                ↓
         Claude generates caller response
                ↓
         OpenAI TTS converts text → MP3
                ↓
         <Play> speaks back to agent
                ↓
         Loop until conversation ends
                ↓
         Claude analyzes transcript → bug_report.md
```

Twilio handles telephony and speech recognition natively — no extra audio infrastructure needed. Flask serves as the webhook server. The caller brain (Claude Haiku) generates responses fast enough (~300–500ms) to stay within natural conversational timing.

## Setup

### 1. Accounts needed

- [Twilio](https://twilio.com) — buy a phone number to call from (~$1/month). Must be a paid account to call arbitrary numbers.
- [Anthropic](https://console.anthropic.com) — Claude API for caller simulation and bug analysis
- [OpenAI](https://platform.openai.com) — TTS for realistic voice output
- [ngrok](https://ngrok.com) — free tier to expose your local Flask server to Twilio webhooks

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Fill in your API keys in .env
```

### 4. Start ngrok

```bash
ngrok http 5000
```

Copy the `https://xxxx.ngrok-free.app` URL into `.env` as `BASE_URL`.

## Running

**Terminal 1** — Flask server:
```bash
python app.py
```

**Terminal 2** — Place calls:
```bash
python call.py all                    # Run all 12 scenarios (90s gap between calls)
python call.py appointment_scheduling # Run a single scenario
```

**After all calls finish** — download MP3 recordings:
```bash
python download_recordings.py
```

Transcripts are saved to `recordings/` after every turn. Bug report is at `recordings/bug_report.md`.

## Scenarios (12 built-in)

| Scenario | Persona | Goal |
|---|---|---|
| `appointment_scheduling` | Sarah Johnson, 34 | Schedule a new routine checkup |
| `appointment_reschedule` | Mark Davis, 45 | Reschedule Monday appointment |
| `appointment_cancel` | Lisa Chen, 29 | Cancel Friday appointment |
| `medication_refill` | James Miller, 58 | Refill Lisinopril 10mg |
| `office_hours` | Emily Rodriguez, 38 | Ask about hours and Saturday availability |
| `insurance_question` | Robert Thompson, 52 | Verify insurance is accepted |
| `location_directions` | Maria Gonzalez, 41 | Get address and parking info |
| `urgent_appointment` | David Kim, 33 | Same-day appointment for suspected illness |
| `angry_patient` | Tom Bradley, 47 | Frustrated about missing lab results |
| `vague_request` | Jennifer White, 36 | Doesn't know what kind of appointment she needs |
| `multiple_requests` | Alex Turner, 44 | Schedule appointment + medication refill |
| `weekend_appointment` | Chris Evans, 31 | Tries to book on a weekend |

Scenarios are defined in `scenarios.py` — easy to add new ones or adapt to non-healthcare use cases.

## Customizing for Your Agent

1. Open `scenarios.py` and update the `system_prompt` for each scenario to match your agent's domain
2. Set `TO_NUMBER` in `call.py` to your agent's phone number
3. Add or remove scenarios as needed

The bot adapts to any industry — healthcare, insurance, banking, retail support, etc.

## Output

After each call you get:
- `recordings/transcript_<scenario>_<call_id>.txt` — full conversation transcript
- `recordings/<call_id>_<recording_id>.mp3` — audio recording of the call
- `recordings/bug_report.md` — auto-generated QA findings for every call

### Example bug report entry

```
## appointment_scheduling — Call CA1a2b3c
**Date:** 2026-06-22T10:30:00

ISSUE: Agent confirmed appointment without verifying patient identity
SEVERITY: High
DETAIL: The agent booked an appointment without asking for date of birth
or any identifying information. Standard practice requires identity
verification before accessing or modifying appointment records.
```

## Environment Variables

| Variable | Description |
|---|---|
| `TWILIO_ACCOUNT_SID` | Twilio account SID (starts with AC) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Your Twilio number in E.164 format |
| `ANTHROPIC_API_KEY` | Anthropic API key (for Claude) |
| `OPENAI_API_KEY` | OpenAI API key (for TTS) |
| `BASE_URL` | Your ngrok HTTPS URL (no trailing slash) |
