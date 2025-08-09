import os
from typing import Optional
import boto3
from botocore.exceptions import ClientError

class Config:
    """Configuration class for ClipGremlin bot."""
    
    def __init__(self):
        self.twitch_client_id = os.getenv('TWITCH_CLIENT_ID')
        self.twitch_client_secret = os.getenv('TWITCH_CLIENT_SECRET')
        self.twitch_bot_token = os.getenv('TWITCH_BOT_TOKEN')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.channel_name = os.getenv('CHANNEL_NAME')
        
        # AWS configuration
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.secrets_manager_enabled = os.getenv('USE_SECRETS_MANAGER', 'false').lower() == 'true'
        
        # Bot settings
        self.silence_duration = int(os.getenv('SILENCE_DURATION', '60'))  # seconds
        self.max_message_rate = int(os.getenv('MAX_MESSAGE_RATE', '20'))  # messages per 30 seconds
        self.rate_limit_window = int(os.getenv('RATE_LIMIT_WINDOW', '30'))  # seconds
        self.audio_chunk_duration = int(os.getenv('AUDIO_CHUNK_DURATION', '10'))  # seconds
        self.max_audio_size_mb = int(os.getenv('MAX_AUDIO_SIZE_MB', '25'))  # MB
        
        # Load secrets from AWS Secrets Manager if enabled
        if self.secrets_manager_enabled:
            self._load_secrets_from_aws()
    
    def _load_secrets_from_aws(self):
        """Load secrets from AWS Secrets Manager."""
        try:
            session = boto3.session.Session()
            client = session.client(
                service_name='secretsmanager',
                region_name=self.aws_region
            )
            
            # Load Twitch secrets
            twitch_secret = client.get_secret_value(SecretId='clipgremlin/twitch')
            twitch_data = eval(twitch_secret['SecretString'])
            self.twitch_client_id = twitch_data.get('client_id')
            self.twitch_client_secret = twitch_data.get('client_secret')
            self.twitch_bot_token = twitch_data.get('bot_token')
            
            # Load OpenAI secret
            openai_secret = client.get_secret_value(SecretId='clipgremlin/openai')
            openai_data = eval(openai_secret['SecretString'])
            self.openai_api_key = openai_data.get('api_key')
            
        except ClientError as e:
            print(f"Failed to load secrets from AWS: {e}")
    
    def validate(self) -> bool:
        """Validate that all required configuration is present."""
        required_fields = [
            'twitch_client_id',
            'twitch_client_secret', 
            'twitch_bot_token',
            'openai_api_key',
            'channel_name'
        ]
        
        missing_fields = []
        for field in required_fields:
            if not getattr(self, field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"Missing required configuration: {missing_fields}")
            return False
        
        return True

# Global config instance
config = Config()
