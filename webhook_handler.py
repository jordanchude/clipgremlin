"""
AWS Lambda handler for Twitch EventSub webhooks.
Handles stream.online and stream.offline events to start/stop Fargate tasks.
"""

import json
import logging
import os
import boto3
from typing import Dict, Any, Optional
import hashlib
import hmac

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# AWS clients
ecs_client = boto3.client('ecs')
secrets_client = boto3.client('secretsmanager')

# Configuration
CLUSTER_NAME = os.environ.get('ECS_CLUSTER_NAME', 'clipgremlin-cluster')
TASK_DEFINITION = os.environ.get('ECS_TASK_DEFINITION', 'clipgremlin-task')
SUBNET_IDS = os.environ.get('SUBNET_IDS', '').split(',')
SECURITY_GROUP_IDS = os.environ.get('SECURITY_GROUP_IDS', '').split(',')
WEBHOOK_SECRET = os.environ.get('TWITCH_WEBHOOK_SECRET')

def verify_webhook_signature(headers: Dict[str, str], body: str) -> bool:
    """
    Verify the Twitch webhook signature.
    
    Args:
        headers: Request headers
        body: Request body
        
    Returns:
        True if signature is valid
    """
    try:
        signature = headers.get('Twitch-Eventsub-Message-Signature', '')
        timestamp = headers.get('Twitch-Eventsub-Message-Timestamp', '')
        message_id = headers.get('Twitch-Eventsub-Message-Id', '')
        
        if not all([signature, timestamp, message_id, WEBHOOK_SECRET]):
            logger.error("Missing required headers or webhook secret")
            return False
        
        # Create the message to verify
        message = message_id + timestamp + body
        
        # Calculate expected signature
        expected_signature = 'sha256=' + hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False

def start_fargate_task(channel_name: str) -> Optional[str]:
    """
    Start a Fargate task for the given channel.
    
    Args:
        channel_name: Twitch channel name
        
    Returns:
        Task ARN if successful, None otherwise
    """
    try:
        logger.info(f"Starting Fargate task for channel: {channel_name}")
        
        response = ecs_client.run_task(
            cluster=CLUSTER_NAME,
            taskDefinition=TASK_DEFINITION,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': SUBNET_IDS,
                    'securityGroups': SECURITY_GROUP_IDS,
                    'assignPublicIp': 'ENABLED'
                }
            },
            overrides={
                'containerOverrides': [
                    {
                        'name': 'clipgremlin',
                        'environment': [
                            {
                                'name': 'CHANNEL_NAME',
                                'value': channel_name
                            }
                        ]
                    }
                ]
            },
            tags=[
                {
                    'key': 'Channel',
                    'value': channel_name
                },
                {
                    'key': 'Service',
                    'value': 'ClipGremlin'
                }
            ]
        )
        
        task_arn = response['tasks'][0]['taskArn']
        logger.info(f"Started task: {task_arn}")
        return task_arn
        
    except Exception as e:
        logger.error(f"Error starting Fargate task: {e}")
        return None

def stop_fargate_tasks(channel_name: str) -> int:
    """
    Stop all Fargate tasks for the given channel.
    
    Args:
        channel_name: Twitch channel name
        
    Returns:
        Number of tasks stopped
    """
    try:
        logger.info(f"Stopping Fargate tasks for channel: {channel_name}")
        
        # List running tasks
        response = ecs_client.list_tasks(
            cluster=CLUSTER_NAME,
            desiredStatus='RUNNING'
        )
        
        tasks_stopped = 0
        
        for task_arn in response['taskArns']:
            # Get task details
            task_details = ecs_client.describe_tasks(
                cluster=CLUSTER_NAME,
                tasks=[task_arn]
            )
            
            # Check if task is for this channel
            for task in task_details['tasks']:
                for tag in task.get('tags', []):
                    if tag['key'] == 'Channel' and tag['value'] == channel_name:
                        # Stop the task
                        ecs_client.stop_task(
                            cluster=CLUSTER_NAME,
                            task=task_arn,
                            reason=f'Stream offline for channel {channel_name}'
                        )
                        tasks_stopped += 1
                        logger.info(f"Stopped task: {task_arn}")
                        break
        
        return tasks_stopped
        
    except Exception as e:
        logger.error(f"Error stopping Fargate tasks: {e}")
        return 0

def handle_stream_online(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stream.online event."""
    try:
        broadcaster_user_name = event_data['broadcaster_user_name']
        logger.info(f"Stream online event for: {broadcaster_user_name}")
        
        task_arn = start_fargate_task(broadcaster_user_name)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Started task for {broadcaster_user_name}',
                'task_arn': task_arn
            })
        }
        
    except Exception as e:
        logger.error(f"Error handling stream online event: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_stream_offline(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle stream.offline event."""
    try:
        broadcaster_user_name = event_data['broadcaster_user_name']
        logger.info(f"Stream offline event for: {broadcaster_user_name}")
        
        tasks_stopped = stop_fargate_tasks(broadcaster_user_name)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Stopped {tasks_stopped} tasks for {broadcaster_user_name}',
                'tasks_stopped': tasks_stopped
            })
        }
        
    except Exception as e:
        logger.error(f"Error handling stream offline event: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Twitch EventSub webhooks.
    
    Args:
        event: Lambda event
        context: Lambda context
        
    Returns:
        HTTP response
    """
    try:
        logger.info(f"Received webhook event: {json.dumps(event)}")
        
        # Extract headers and body
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        # Verify webhook signature
        if not verify_webhook_signature(headers, body):
            logger.error("Invalid webhook signature")
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Invalid signature'})
            }
        
        # Parse the body
        webhook_data = json.loads(body)
        
        # Handle webhook challenge
        if 'challenge' in webhook_data:
            logger.info("Responding to webhook challenge")
            return {
                'statusCode': 200,
                'body': webhook_data['challenge']
            }
        
        # Handle subscription events
        subscription = webhook_data.get('subscription', {})
        event_data = webhook_data.get('event', {})
        
        subscription_type = subscription.get('type')
        
        if subscription_type == 'stream.online':
            return handle_stream_online(event_data)
        elif subscription_type == 'stream.offline':
            return handle_stream_offline(event_data)
        else:
            logger.warning(f"Unhandled subscription type: {subscription_type}")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Event ignored'})
            }
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
