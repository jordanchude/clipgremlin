#!/bin/bash

# ClipGremlin Deployment Script
set -e

# Configuration
STACK_NAME="clipgremlin"
REGION="us-east-1"
IMAGE_TAG="latest"

echo "🚀 Starting ClipGremlin deployment..."

# Check if required tools are installed
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI is required but not installed."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed."; exit 1; }

# Check if CloudFormation stack exists
if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION >/dev/null 2>&1; then
    echo "📦 Stack $STACK_NAME exists, updating..."
    STACK_ACTION="update-stack"
else
    echo "📦 Stack $STACK_NAME doesn't exist, creating..."
    STACK_ACTION="create-stack"
fi

# Get ECR repository URI
echo "🔍 Getting ECR repository URI..."
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepository`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -z "$ECR_URI" ]; then
    echo "⚠️ ECR repository not found in existing stack, will be created during stack deployment"
fi

# Deploy/Update CloudFormation stack
echo "☁️ Deploying CloudFormation stack..."
read -p "Enter Twitch Client ID: " TWITCH_CLIENT_ID
read -s -p "Enter Twitch Client Secret: " TWITCH_CLIENT_SECRET
echo
read -s -p "Enter Twitch Bot Token: " TWITCH_BOT_TOKEN
echo
read -s -p "Enter OpenAI API Key: " OPENAI_API_KEY
echo
read -s -p "Enter Twitch Webhook Secret: " TWITCH_WEBHOOK_SECRET
echo
read -p "Enter VPC ID: " VPC_ID
read -p "Enter Subnet IDs (comma-separated): " SUBNET_IDS

aws cloudformation $STACK_ACTION \
    --stack-name $STACK_NAME \
    --region $REGION \
    --template-body file://cloudformation.yml \
    --parameters \
        ParameterKey=TwitchClientId,ParameterValue="$TWITCH_CLIENT_ID" \
        ParameterKey=TwitchClientSecret,ParameterValue="$TWITCH_CLIENT_SECRET" \
        ParameterKey=TwitchBotToken,ParameterValue="$TWITCH_BOT_TOKEN" \
        ParameterKey=OpenAIApiKey,ParameterValue="$OPENAI_API_KEY" \
        ParameterKey=TwitchWebhookSecret,ParameterValue="$TWITCH_WEBHOOK_SECRET" \
        ParameterKey=VpcId,ParameterValue="$VPC_ID" \
        ParameterKey=SubnetIds,ParameterValue="$SUBNET_IDS" \
    --capabilities CAPABILITY_IAM

echo "⏳ Waiting for stack deployment to complete..."
aws cloudformation wait stack-${STACK_ACTION%-stack}-complete \
    --stack-name $STACK_NAME \
    --region $REGION

# Get ECR repository URI after stack creation/update
echo "🔍 Getting ECR repository URI..."
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepository`].OutputValue' \
    --output text)

echo "📦 ECR Repository: $ECR_URI"

# Build and push Docker image
echo "🐳 Building Docker image..."
docker build -t clipgremlin:$IMAGE_TAG .

echo "🏷️ Tagging image for ECR..."
docker tag clipgremlin:$IMAGE_TAG $ECR_URI:$IMAGE_TAG

echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

echo "📤 Pushing image to ECR..."
docker push $ECR_URI:$IMAGE_TAG

# Update ECS service to use new image (force new deployment)
echo "🔄 Forcing ECS service update..."
CLUSTER_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' \
    --output text)

# Get webhook URL for EventSub setup
WEBHOOK_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`WebhookURL`].OutputValue' \
    --output text)

echo "✅ Deployment completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Configure Twitch EventSub webhooks using this URL:"
echo "   $WEBHOOK_URL"
echo ""
echo "2. Register webhooks for your target channels using Twitch CLI:"
echo "   twitch api post eventsub/subscriptions -b '{\"type\":\"stream.online\",\"version\":\"1\",\"condition\":{\"broadcaster_user_id\":\"USER_ID\"},\"transport\":{\"method\":\"webhook\",\"callback\":\"$WEBHOOK_URL\",\"secret\":\"YOUR_WEBHOOK_SECRET\"}}'"
echo ""
echo "3. Monitor the deployment:"
echo "   aws logs tail /ecs/clipgremlin --follow --region $REGION"
echo ""
echo "🎉 ClipGremlin is ready to cause some mischief! 😈"
