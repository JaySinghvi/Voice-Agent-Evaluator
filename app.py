import os
import time
from datetime import datetime
from flask import Flask, request, Response, send_file
from twilio.twiml.voice_response import VoiceResponse, Gather
from anthropic import Anthropic
from openai import OpenAI
from dotenv import load_dotenv
from scenarios import SCENARIOS

load_dotenv()

app = Flask(__name__)
anthropic = Anthropic()
openai_client = OpenAI()

BASE_URL = os.environ["BASE_URL"]

# In-memory store: call_sid -> conversation state
conversations = {}

MAX_TURNS = 20  # safety limit per call


@app.route("/answer", methods=["POST"])
def answer():
    call_sid = request.form.get("CallSid")
    scenario_name = request.args.get("scenario", "appointment_scheduling")
    scenario = SCENARIOS.get(scenario_name, SCENARIOS["appointment_scheduling"])

    conversations[call_sid] = {
        "messages": [],
        "scenario": scenario,
        "transcript": [],
        "turns": 0,
        "started_at": datetime.now().isoformat(),
    }

    print(f"[{call_sid[:8]}] Call started — scenario: {scenario_name}")

    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"/gather?scenario={scenario_name}",
        method="POST",
        speech_timeout="auto",
        speech_model="phone_call",
        language="en-US",
        timeout=10,
    )
    response.append(gather)
    # Fallback: if agent doesn't speak within timeout, re-listen
    response.redirect(f"/gather?scenario={scenario_name}&no_speech=true", method="POST")

    return Response(str(response), mimetype="text/xml")


@app.route("/gather", methods=["POST"])
def gather():
    call_sid = request.form.get("CallSid")
    speech_result = request.form.get("SpeechResult", "").strip()
    no_speech = request.args.get("no_speech") == "true"
    scenario_name = request.args.get("scenario", "appointment_scheduling")

    conv = conversations.get(call_sid)
    if not conv:
        # Shouldn't happen, but recover gracefully
        scenario = SCENARIOS.get(scenario_name, SCENARIOS["appointment_scheduling"])
        conv = {
            "messages": [],
            "scenario": scenario,
            "transcript": [],
            "turns": 0,
            "started_at": datetime.now().isoformat(),
        }
        conversations[call_sid] = conv

    response = VoiceResponse()

    # No speech detected — just re-listen
    if no_speech or not speech_result:
        gather = Gather(
            input="speech",
            action=f"/gather?scenario={scenario_name}",
            method="POST",
            speech_timeout="auto",
            speech_model="phone_call",
            language="en-US",
            timeout=10,
        )
        response.append(gather)
        response.redirect(f"/gather?scenario={scenario_name}&no_speech=true", method="POST")
        return Response(str(response), mimetype="text/xml")

    # Safety: end call if too many turns
    if conv["turns"] >= MAX_TURNS:
        _speak(response, "Thank you, goodbye.", call_sid)
        response.hangup()
        return Response(str(response), mimetype="text/xml")

    # Log what the agent said
    print(f"[{call_sid[:8]}] Agent: {speech_result}")
    conv["transcript"].append({"speaker": "Agent", "text": speech_result})
    conv["messages"].append({"role": "user", "content": speech_result})
    conv["turns"] += 1

    # Ask Claude to generate the patient's next reply
    claude_resp = anthropic.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        system=conv["scenario"]["system_prompt"],
        messages=conv["messages"],
    )
    patient_text = claude_resp.content[0].text.strip()

    # Check for end-of-call signal
    end_call = "[END_CALL]" in patient_text
    patient_text = patient_text.replace("[END_CALL]", "").strip()

    print(f"[{call_sid[:8]}] Patient: {patient_text}")
    conv["transcript"].append({"speaker": "Patient", "text": patient_text})
    conv["messages"].append({"role": "assistant", "content": patient_text})

    _save_transcript(call_sid, conv)

    if end_call:
        _speak(response, patient_text, call_sid)
        response.hangup()
    else:
        _speak(response, patient_text, call_sid)
        gather = Gather(
            input="speech",
            action=f"/gather?scenario={scenario_name}",
            method="POST",
            speech_timeout="auto",
            speech_model="phone_call",
            language="en-US",
            timeout=10,
        )
        response.append(gather)
        response.redirect(f"/gather?scenario={scenario_name}&no_speech=true", method="POST")

    return Response(str(response), mimetype="text/xml")


@app.route("/status", methods=["POST"])
def status():
    call_sid = request.form.get("CallSid")
    call_status = request.form.get("CallStatus")
    recording_url = request.form.get("RecordingUrl")

    print(f"[{call_sid[:8]}] Status: {call_status}")
    conv = conversations.get(call_sid)

    if recording_url and conv:
        mp3_url = recording_url + ".mp3"
        print(f"[{call_sid[:8]}] Recording: {mp3_url}")
        conv["recording_url"] = mp3_url
        _save_transcript(call_sid, conv)

    if conv and conv.get("transcript"):
        print(f"[{call_sid[:8]}] Running bug analysis...")
        _analyze_transcript(call_sid, conv)

    return "", 200


@app.route("/audio/<filename>", methods=["GET"])
def serve_audio(filename):
    path = os.path.join("recordings", "audio", filename)
    return send_file(path, mimetype="audio/mpeg")


def _speak(response, text, call_sid):
    os.makedirs(os.path.join("recordings", "audio"), exist_ok=True)
    filename = f"{call_sid[:8]}_{int(time.time())}.mp3"
    path = os.path.join("recordings", "audio", filename)
    audio = openai_client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text,
    )
    with open(path, "wb") as f:
        f.write(audio.content)
    response.play(f"{BASE_URL}/audio/{filename}")


def _save_transcript(call_sid, conv):
    os.makedirs("recordings", exist_ok=True)
    scenario_name = conv["scenario"]["name"]
    path = f"recordings/transcript_{scenario_name}_{call_sid[:8]}.txt"
    with open(path, "w") as f:
        f.write(f"Scenario : {scenario_name}\n")
        f.write(f"Call SID : {call_sid}\n")
        f.write(f"Started  : {conv['started_at']}\n")
        if "recording_url" in conv:
            f.write(f"Recording: {conv['recording_url']}\n")
        f.write("=" * 60 + "\n\n")
        for turn in conv["transcript"]:
            f.write(f"{turn['speaker']}: {turn['text']}\n\n")


def _analyze_transcript(call_sid, conv):
    scenario_name = conv["scenario"]["name"]

    # Build a plain-text version of the transcript for the prompt
    transcript_text = ""
    for turn in conv["transcript"]:
        transcript_text += f"{turn['speaker']}: {turn['text']}\n\n"

    system_prompt = (
        "You are a QA evaluator testing a medical AI phone agent. "
        "Your job is to review a conversation transcript and identify bugs, errors, or quality issues "
        "in the Agent's responses. Focus only on what the Agent said — not the Patient. "
        "For each issue found, output it in this exact format:\n\n"
        "ISSUE: <one-line summary>\n"
        "SEVERITY: High | Medium | Low\n"
        "DETAIL: <what happened, why it's a problem, what the correct behavior should be>\n\n"
        "If no issues are found, write: NO ISSUES FOUND\n"
        "Be specific and cite exact quotes from the Agent where relevant."
    )

    user_prompt = (
        f"Scenario being tested: {scenario_name}\n\n"
        f"Transcript:\n{transcript_text}"
    )

    resp = anthropic.messages.create(
        model="claude-sonnet-4-6-20251001",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    analysis = resp.content[0].text.strip()

    print(f"[{call_sid[:8]}] Analysis complete.")

    # Append to the single bug_report.md file
    os.makedirs("recordings", exist_ok=True)
    with open("recordings/bug_report.md", "a", encoding="utf-8") as f:
        f.write(f"## {scenario_name} — Call {call_sid[:8]}\n")
        f.write(f"**Date:** {conv['started_at']}\n")
        if "recording_url" in conv:
            f.write(f"**Recording:** {conv['recording_url']}\n")
        f.write("\n")
        f.write(analysis)
        f.write("\n\n---\n\n")

    print(f"[{call_sid[:8]}] Bug report updated → recordings/bug_report.md")


if __name__ == "__main__":
    app.run(port=5000, debug=True)
