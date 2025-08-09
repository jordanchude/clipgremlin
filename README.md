# ClipGremlin 😈

A mischievous Twitch bot that transcribes live audio and drops PG-13 prompts during chat silence.

## Overview

ClipGremlin is a stateless Python bot that:
- Joins Twitch channels when they go live (via EventSub webhooks)
- Transcribes live audio using OpenAI Whisper-Turbo
- Monitors chat for periods of silence (60 seconds by default)
- Generates and posts mischievous but friendly prompts in the streamer's language
- Can be paused/resumed by moderators with `!gremlin pause`/`!gremlin resume`
- Automatically shuts down when streams end

## Architecture

```
Twitch EventSub → AWS Lambda (webhook validator)
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
```

## Features

- ✅ **Real-time audio transcription** with Whisper-Turbo (~300ms latency)
- ✅ **Multi-language support** - detects and responds in streamer's language
- ✅ **Rate limiting** - respects Twitch's 20 messages per 30 seconds limit
- ✅ **AutoMod integration** - checks generated content before posting
- ✅ **Moderator controls** - pause/resume functionality
- ✅ **AWS Fargate deployment** - scales to zero when streams are offline
- ✅ **Health monitoring** - built-in health checks and metrics

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/clip-gremlin.git
   cd clip-gremlin
   ```

2. **Set up environment**
   ```bash
   cp env.example .env
   # Edit .env with your credentials
   ```

3. **Run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

### Required Environment Variables

```bash
# Twitch Configuration
TWITCH_CLIENT_ID=your_twitch_client_id
TWITCH_CLIENT_SECRET=your_twitch_client_secret
TWITCH_BOT_TOKEN=oauth:your_bot_token
CHANNEL_NAME=target_channel_name

# OpenAI Configuration
OPENAI_API_KEY=sk-your_openai_api_key

# Optional Settings
SILENCE_DURATION=60              # Seconds of silence before prompt
MAX_MESSAGE_RATE=20             # Max messages per 30 seconds
AUDIO_CHUNK_DURATION=10         # Audio chunk size in seconds
```

## Production Deployment

### AWS Infrastructure

1. **Deploy CloudFormation stack**
   ```bash
   aws cloudformation create-stack \
     --stack-name clipgremlin \
     --template-body file://cloudformation.yml \
     --parameters \
       ParameterKey=TwitchClientId,ParameterValue=your_client_id \
       ParameterKey=TwitchClientSecret,ParameterValue=your_client_secret \
       ParameterKey=TwitchBotToken,ParameterValue=your_bot_token \
       ParameterKey=OpenAIApiKey,ParameterValue=your_openai_key \
       ParameterKey=TwitchWebhookSecret,ParameterValue=your_webhook_secret \
       ParameterKey=VpcId,ParameterValue=vpc-xxxxxxxx \
       ParameterKey=SubnetIds,ParameterValue=subnet-xxxxxxxx,subnet-yyyyyyyy \
     --capabilities CAPABILITY_IAM
   ```

2. **Build and push Docker image**
   ```bash
   # Get ECR repository URI from CloudFormation outputs
   ECR_URI=$(aws cloudformation describe-stacks \
     --stack-name clipgremlin \
     --query 'Stacks[0].Outputs[?OutputKey==`ECRRepository`].OutputValue' \
     --output text)

   # Build and push
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI
   docker build -t clipgremlin .
   docker tag clipgremlin:latest $ECR_URI:latest
   docker push $ECR_URI:latest
   ```

3. **Configure Twitch EventSub webhooks**
   ```bash
   # Get webhook URL from CloudFormation outputs
   WEBHOOK_URL=$(aws cloudformation describe-stacks \
     --stack-name clipgremlin \
     --query 'Stacks[0].Outputs[?OutputKey==`WebhookURL`].OutputValue' \
     --output text)

   # Register webhooks using Twitch CLI or API
   twitch api post eventsub/subscriptions \
     -b '{"type":"stream.online","version":"1","condition":{"broadcaster_user_id":"USER_ID"},"transport":{"method":"webhook","callback":"'$WEBHOOK_URL'","secret":"YOUR_WEBHOOK_SECRET"}}'
   ```

## Bot Commands

| Command | Permission | Description |
|---------|-----------|-------------|
| `!gremlin pause` | Moderator/Broadcaster | Mute the bot (responds: "Gremlin muted 😶") |
| `!gremlin resume` | Moderator/Broadcaster | Unmute the bot (responds: "Gremlin unleashed 😈") |

## Configuration

### Audio Processing
- **Chunk Duration**: 10 seconds (configurable)
- **Sample Rate**: 16kHz mono
- **Max File Size**: 25MB (Whisper API limit)
- **Format**: WAV PCM 16-bit

### Rate Limiting
- **Unverified Bot**: 20 messages per 30 seconds
- **Verified Bot**: 100 messages per 30 seconds (future enhancement)
- **Silence Detection**: 60 seconds (configurable)

### Language Support
Automatically detects and responds in:
- English (en)
- Spanish (es) 
- French (fr)
- German (de)
- And more via Whisper language detection

## Monitoring

### Health Checks
- `GET /health` - Basic health status
- `GET /status` - Detailed bot status
- `GET /metrics` - Prometheus-style metrics

### CloudWatch Metrics
- Task failure alarms
- API quota usage monitoring
- Memory and CPU utilization

## Development

### Project Structure
```
clip-gremlin/
├── main.py                 # Main application entry point
├── config.py              # Configuration management
├── audio_processor.py     # HLS stream capture and processing
├── whisper_client.py      # OpenAI Whisper integration
├── gpt_client.py          # GPT prompt generation
├── twitch_client.py       # Twitch IRC and API client
├── silence_detector.py    # Chat silence monitoring
├── health_check.py        # Health check server
├── webhook_handler.py     # AWS Lambda webhook handler
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container image
├── docker-compose.yml    # Local development
└── cloudformation.yml    # AWS infrastructure
```

### Running Tests
```bash
python -m pytest tests/ -v
```

### Code Quality
```bash
# Linting
flake8 .

# Type checking
mypy .

# Security scanning
bandit -r .
```

## Troubleshooting

### Common Issues

1. **FFmpeg not found**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update && sudo apt-get install ffmpeg
   
   # macOS
   brew install ffmpeg
   ```

2. **Stream URL not accessible**
   - Verify the channel is live
   - Check if the stream has mature content restrictions
   - Ensure network connectivity to Twitch

3. **Rate limiting**
   - Bot will automatically respect rate limits
   - Consider applying for verified bot status

4. **AutoMod blocking prompts**
   - Prompts are designed to be PG-13 and ToS-safe
   - Failed prompts are logged but not retried

### Logs
```bash
# Local development
docker-compose logs -f clipgremlin

# AWS CloudWatch
aws logs tail /ecs/clipgremlin --follow
```

## Security

- All secrets stored in AWS Secrets Manager
- Webhook signatures verified using HMAC
- Container runs as non-root user
- Network security groups restrict access

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This bot is designed to be mischievous but friendly. Always ensure compliance with Twitch's Terms of Service and Community Guidelines. The bot includes content filtering and AutoMod integration to help maintain appropriate behavior.

---

**Made with ❤️ and a bit of mischief 😈**
