"""
ClipGremlin Web Application
Flask-based web interface for streamers to add ClipGremlin to their channels.
"""

import os
import json
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

import boto3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'sqlite:///clipgremlin.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Twitch OAuth configuration
TWITCH_CLIENT_ID = os.environ.get('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.environ.get('TWITCH_CLIENT_SECRET')
TWITCH_REDIRECT_URI = os.environ.get('TWITCH_REDIRECT_URI', 'http://localhost:5000/auth/callback')
TWITCH_SCOPES = ['user:read:email', 'channel:read:subscriptions', 'moderator:read:chatters']

# AWS configuration
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
ECS_CLUSTER_NAME = os.environ.get('ECS_CLUSTER_NAME', 'clipgremlin-cluster')
ECS_TASK_DEFINITION = os.environ.get('ECS_TASK_DEFINITION', 'clipgremlin-task')

# Initialize database
db = SQLAlchemy(app)

class Channel(db.Model):
    """Model for authorized Twitch channels."""
    
    id = db.Column(db.Integer, primary_key=True)
    twitch_user_id = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200))
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    
    # Bot settings
    is_active = db.Column(db.Boolean, default=True)
    silence_duration = db.Column(db.Integer, default=60)
    max_message_rate = db.Column(db.Integer, default=20)
    language_override = db.Column(db.String(10))  # Override auto-detection
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active = db.Column(db.DateTime)
    
    # Task tracking
    current_task_arn = db.Column(db.String(200))
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'is_active': self.is_active,
            'silence_duration': self.silence_duration,
            'max_message_rate': self.max_message_rate,
            'language_override': self.language_override,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None
        }

class BotActivity(db.Model):
    """Model for tracking bot activity and prompts."""
    
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    
    # Activity details
    activity_type = db.Column(db.String(50), nullable=False)  # 'prompt_sent', 'stream_start', 'stream_end', etc.
    message = db.Column(db.Text)
    language_detected = db.Column(db.String(10))
    transcript_snippet = db.Column(db.Text)
    
    # Timestamps
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    channel = db.relationship('Channel', backref=db.backref('activities', lazy=True))

# AWS clients
ecs_client = boto3.client('ecs', region_name=AWS_REGION)

class TwitchAPI:
    """Helper class for Twitch API interactions."""
    
    BASE_URL = 'https://api.twitch.tv/helix'
    TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
    
    @staticmethod
    def get_authorization_url(state: str) -> str:
        """Generate Twitch OAuth authorization URL."""
        params = {
            'client_id': TWITCH_CLIENT_ID,
            'redirect_uri': TWITCH_REDIRECT_URI,
            'response_type': 'code',
            'scope': ' '.join(TWITCH_SCOPES),
            'state': state
        }
        return f'https://id.twitch.tv/oauth2/authorize?{urlencode(params)}'
    
    @staticmethod
    def exchange_code_for_token(code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access token."""
        try:
            data = {
                'client_id': TWITCH_CLIENT_ID,
                'client_secret': TWITCH_CLIENT_SECRET,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': TWITCH_REDIRECT_URI
            }
            
            response = requests.post(TwitchAPI.TOKEN_URL, data=data)
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            return None
    
    @staticmethod
    def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
        """Get user information from Twitch API."""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Client-Id': TWITCH_CLIENT_ID
            }
            
            response = requests.get(f'{TwitchAPI.BASE_URL}/users', headers=headers)
            response.raise_for_status()
            data = response.json()
            
            return data['data'][0] if data['data'] else None
            
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    @staticmethod
    def validate_token(access_token: str) -> bool:
        """Validate access token."""
        try:
            headers = {'Authorization': f'OAuth {access_token}'}
            response = requests.get('https://id.twitch.tv/oauth2/validate', headers=headers)
            return response.status_code == 200
        except:
            return False

class ECSManager:
    """Helper class for managing ECS tasks."""
    
    @staticmethod
    def start_bot_task(channel: Channel) -> Optional[str]:
        """Start a bot task for the given channel."""
        try:
            logger.info(f"Starting bot task for channel: {channel.username}")
            
            response = ecs_client.run_task(
                cluster=ECS_CLUSTER_NAME,
                taskDefinition=ECS_TASK_DEFINITION,
                launchType='FARGATE',
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': os.environ.get('SUBNET_IDS', '').split(','),
                        'securityGroups': [os.environ.get('SECURITY_GROUP_ID', '')],
                        'assignPublicIp': 'ENABLED'
                    }
                },
                overrides={
                    'containerOverrides': [
                        {
                            'name': 'clipgremlin',
                            'environment': [
                                {'name': 'CHANNEL_NAME', 'value': channel.username},
                                {'name': 'SILENCE_DURATION', 'value': str(channel.silence_duration)},
                                {'name': 'MAX_MESSAGE_RATE', 'value': str(channel.max_message_rate)},
                                {'name': 'TWITCH_BOT_TOKEN', 'value': channel.access_token}
                            ]
                        }
                    ]
                },
                tags=[
                    {'key': 'Channel', 'value': channel.username},
                    {'key': 'ChannelId', 'value': str(channel.id)},
                    {'key': 'Service', 'value': 'ClipGremlin'}
                ]
            )
            
            task_arn = response['tasks'][0]['taskArn']
            logger.info(f"Started task: {task_arn}")
            
            # Update channel with task ARN
            channel.current_task_arn = task_arn
            channel.last_active = datetime.utcnow()
            db.session.commit()
            
            return task_arn
            
        except Exception as e:
            logger.error(f"Error starting bot task: {e}")
            return None
    
    @staticmethod
    def stop_bot_task(channel: Channel) -> bool:
        """Stop the bot task for the given channel."""
        try:
            if not channel.current_task_arn:
                return True
            
            logger.info(f"Stopping bot task for channel: {channel.username}")
            
            ecs_client.stop_task(
                cluster=ECS_CLUSTER_NAME,
                task=channel.current_task_arn,
                reason=f'Stopped by user: {channel.username}'
            )
            
            # Clear task ARN
            channel.current_task_arn = None
            db.session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping bot task: {e}")
            return False

# Routes
@app.route('/')
def index():
    """Landing page."""
    return render_template('index.html')

@app.route('/features')
def features():
    """Features page."""
    return render_template('features.html')

@app.route('/pricing')
def pricing():
    """Pricing page."""
    return render_template('pricing.html')

@app.route('/auth/login')
def login():
    """Initiate Twitch OAuth flow."""
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
    auth_url = TwitchAPI.get_authorization_url(state)
    return redirect(auth_url)

@app.route('/auth/callback')
def oauth_callback():
    """Handle Twitch OAuth callback."""
    # Verify state parameter
    if request.args.get('state') != session.get('oauth_state'):
        flash('Invalid OAuth state', 'error')
        return redirect(url_for('index'))
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        flash('Authorization failed', 'error')
        return redirect(url_for('index'))
    
    # Exchange code for token
    token_data = TwitchAPI.exchange_code_for_token(code)
    if not token_data:
        flash('Failed to get access token', 'error')
        return redirect(url_for('index'))
    
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    
    # Get user info
    user_info = TwitchAPI.get_user_info(access_token)
    if not user_info:
        flash('Failed to get user information', 'error')
        return redirect(url_for('index'))
    
    # Create or update channel
    channel = Channel.query.filter_by(twitch_user_id=user_info['id']).first()
    
    if channel:
        # Update existing channel
        channel.access_token = access_token
        channel.refresh_token = refresh_token
        channel.email = user_info.get('email')
        channel.updated_at = datetime.utcnow()
    else:
        # Create new channel
        channel = Channel(
            twitch_user_id=user_info['id'],
            username=user_info['login'],
            display_name=user_info['display_name'],
            email=user_info.get('email'),
            access_token=access_token,
            refresh_token=refresh_token
        )
        db.session.add(channel)
    
    db.session.commit()
    
    # Store channel ID in session
    session['channel_id'] = channel.id
    
    flash(f'Successfully connected ClipGremlin to {channel.display_name}\'s channel!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    """Streamer dashboard."""
    channel_id = session.get('channel_id')
    if not channel_id:
        return redirect(url_for('login'))
    
    channel = Channel.query.get(channel_id)
    if not channel:
        session.pop('channel_id', None)
        return redirect(url_for('login'))
    
    # Get recent activity
    recent_activity = BotActivity.query.filter_by(channel_id=channel.id)\
        .order_by(BotActivity.timestamp.desc())\
        .limit(20).all()
    
    return render_template('dashboard.html', channel=channel, recent_activity=recent_activity)

@app.route('/api/bot/toggle', methods=['POST'])
def toggle_bot():
    """Toggle bot on/off for the channel."""
    channel_id = session.get('channel_id')
    if not channel_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    if channel.is_active:
        # Stop the bot
        success = ECSManager.stop_bot_task(channel)
        if success:
            channel.is_active = False
            db.session.commit()
            return jsonify({'status': 'stopped', 'message': 'ClipGremlin has been stopped'})
        else:
            return jsonify({'error': 'Failed to stop bot'}), 500
    else:
        # Start the bot
        task_arn = ECSManager.start_bot_task(channel)
        if task_arn:
            channel.is_active = True
            db.session.commit()
            return jsonify({'status': 'started', 'message': 'ClipGremlin has been started', 'task_arn': task_arn})
        else:
            return jsonify({'error': 'Failed to start bot'}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """Get or update channel settings."""
    channel_id = session.get('channel_id')
    if not channel_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404
    
    if request.method == 'GET':
        return jsonify(channel.to_dict())
    
    # Update settings
    data = request.get_json()
    
    if 'silence_duration' in data:
        channel.silence_duration = max(30, min(300, int(data['silence_duration'])))
    
    if 'max_message_rate' in data:
        channel.max_message_rate = max(1, min(20, int(data['max_message_rate'])))
    
    if 'language_override' in data:
        channel.language_override = data['language_override'] if data['language_override'] else None
    
    channel.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'message': 'Settings updated successfully'})

@app.route('/api/activity')
def get_activity():
    """Get recent bot activity."""
    channel_id = session.get('channel_id')
    if not channel_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    activity = BotActivity.query.filter_by(channel_id=channel_id)\
        .order_by(BotActivity.timestamp.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'activities': [
            {
                'id': a.id,
                'type': a.activity_type,
                'message': a.message,
                'language': a.language_detected,
                'timestamp': a.timestamp.isoformat()
            }
            for a in activity.items
        ],
        'total': activity.total,
        'pages': activity.pages,
        'current_page': page
    })

@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    flash('Successfully logged out', 'info')
    return redirect(url_for('index'))

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    })

# Initialize database
@app.before_first_request
def create_tables():
    """Create database tables."""
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
