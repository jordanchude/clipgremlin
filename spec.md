CLIPGREMLIN – DEVELOPER-READY SPECIFICATION
==========================================

OVERVIEW
• ClipGremlin is a stateless Python bot that joins a Twitch channel, transcribes the live audio with OpenAI Whisper-Turbo, and—after 60 seconds of total chat silence—drops exactly one mischievous PG-13 prompt in the same language the streamer is speaking.  
  – Twitch’s unverified-bot cap is 20 chat messages per 30 seconds; exceeding it mutes the bot for 30 minutes. :contentReference[oaicite:0]{index=0}  
  – The spoken-language code comes directly from the Whisper JSON response. :contentReference[oaicite:1]{index=1}  
• Broadcaster or moderator can mute / un-mute the bot with `!gremlin pause` and `!gremlin resume`; the bot replies “Gremlin muted 😶” or “Gremlin unleashed 😈” as confirmation.  
• Workers spin up only while the channel is live, triggered by Twitch EventSub’s `stream.online` webhook, and shut down on `stream.offline`, saving compute costs. :contentReference[oaicite:2]{index=2}  

FUNCTIONAL REQUIREMENTS
1. On receiving a `stream.online` EventSub notification, start a Fargate task and join the IRC channel as **ClipGremlin**. :contentReference[oaicite:3]{index=3}  
2. Use `ffmpeg` to pull the low-latency HLS playlist, down-mix to mono 16 kHz WAV, and cut ≤10 second chunks (always < 25 MB per Whisper request). :contentReference[oaicite:4]{index=4}  
3. Send each chunk to Whisper-Turbo; typical end-to-end model latency is ~300 ms. :contentReference[oaicite:5]{index=5}  
4. Maintain a rolling 60-second window of incoming chat messages (in RAM).  
5. When the window shows **zero** messages for 60 seconds, ask GPT-3.5-Turbo for a one-line, PG-13, ToS-safe “troll” question that fits the latest transcript snippet.  
6. Run the candidate text through Twitch’s *Check AutoMod Status* endpoint; if “ALLOW”, post it; if “DENY”, drop it silently. :contentReference[oaicite:6]{index=6}  
7. Accept `!gremlin pause` and `!gremlin resume` commands from broadcaster or moderators only (verified via IRC message tags). :contentReference[oaicite:7]{index=7}  
8. On `stream.offline`, terminate the Fargate task; no state is persisted.

NON-FUNCTIONAL REQUIREMENTS
• Cold-start latency: the first prompt must appear no later than 90 seconds after `stream.online`.  
  – zstd-compressed container layers shorten Fargate startup times significantly. :contentReference[oaicite:8]{index=8}  
• Runtime latency: microphone-to-prompt path must stay under 10 seconds (≈2 s HLS + ≤0.3 s Whisper + GPT call).  
• Statelessness: no database, cache, or disk storage; all runtime data lives in RAM.  
• Resilience: if the task crashes, CloudWatch alarms and EventBridge rules relaunch the definition automatically. :contentReference[oaicite:9]{index=9}  

ARCHITECTURE (ASCII)
Twitch EventSub ──▶ AWS Lambda (webhook validator)  
                      │  
                      ▼  
                AWS Fargate Task  
                ├─ ffmpeg (HLS → WAV)  
                ├─ Whisper-Turbo (speech-to-text)  
                ├─ GPT-3.5-Turbo (prompt craft)  
                └─ IRC / Helix POST (chat message)  
                      ▲  
                      │ AutoMod check  
                      ▼  
                 Twitch Chat Server  

KEY IMPLEMENTATION DETAILS
• Container image: `python:3.11-slim` (~120 MB compressed) plus static `ffmpeg`.  
• Libraries: `openai`, `twitchio`, `aiohttp`, `uvloop`.  
• Secrets: Twitch OAuth client ID/secret and OpenAI key stored in AWS Secrets Manager.  
• Billing: Fargate charges per-second with a one-minute minimum, so idle time costs $0. :contentReference[oaicite:10]{index=10}  
• Username colour: `/color Green`—a preset shade available to any account; no Prime or hex code required. :contentReference[oaicite:11]{index=11}  
• Verified-bot badge (future): raises the cap from 20 to 100 messages per 30 seconds. :contentReference[oaicite:12]{index=12}  

DATA HANDLING
• HLS AAC segments and WAV chunks are discarded immediately after processing.  
• Whisper JSON and GPT payloads are kept in memory only long enough to complete a prompt (<1 minute).  
• No personally identifiable information is stored or logged.  

ERROR-HANDLING STRATEGIES
• Whisper request >25 MB → chunker already enforces ≤10 s slices; log and skip.  
• GPT time-out → exponential back-off (max 2 retries) then abandon that prompt cycle.  
• Rate-limit over-run → delay sends until the rolling 30-second window drops below 20 messages. :contentReference[oaicite:13]{index=13}  
• AutoMod “BLOCK” → do not post alternate wording; wait for next silence event.  
• Fargate task crash → CloudWatch + EventBridge relaunch same task definition. :contentReference[oaicite:14]{index=14}  

TESTING PLAN
• Unit tests: silence-detector edge cases; command-parser privilege checks; AutoMod stub.  
• Integration tests: local sandbox with Twitch IRC test server and prerecorded VOD; verify <10 s latency from audio to prompt.  
• Load tests: 8-hour soak run; ensure memory <200 MiB and message rate never exceeds 20/30 s.  
• Chaos tests: inject Whisper 500 errors; confirm retries then skip.  

OPERATIONAL CHECKLIST
1. Register Twitch account “ClipGremlin” and set `/color Green`. :contentReference[oaicite:15]{index=15}  
2. Create EventSub webhooks for `stream.online` and `stream.offline`. :contentReference[oaicite:16]{index=16}  
3. Store secrets in AWS Secrets Manager.  
4. Build zstd-compressed image; push to ECR. :contentReference[oaicite:17]{index=17}  
5. Deploy Fargate task (0.25 vCPU / 512 MiB) via CloudFormation or Terraform.  
6. Configure CloudWatch alarms for task failure and API quota usage.  

FUTURE EXTENSIONS
• Apply for verified-bot badge to unlock 100 msgs / 30 s. :contentReference[oaicite:18]{index=18}  
• Persist prompt logs to DynamoDB for analytics.  
• Enable automatic clip creation via Helix `POST /helix/clips` when streamers opt-in. :contentReference[oaicite:19]{index=19}  
• Swap Fargate for AWS Lambda SnapStart if sub-20 s cold starts ever become critical.
