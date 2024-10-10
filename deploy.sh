#!/bin/bash
set -x
set -eo pipefail
STACK_NAME=document-processing-bedrock-prompt-flows

# Get accountnumber
ACCOUNT_NUMBER=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="$STACK_NAME"-"$ACCOUNT_NUMBER"

#If the bucket doesn't exist, create it
if ! aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    aws s3 mb s3://"$BUCKET_NAME"
fi

# upload prompt flow files
KEY_PATH=prompt_flows
aws s3 sync ./prompt_flows s3://"$BUCKET_NAME"/"$KEY_PATH"

# build and deploy
sam build
sam deploy --capabilities CAPABILITY_NAMED_IAM --s3-bucket "$BUCKET_NAME" --parameter-overrides PromptFlowsBucket="$BUCKET_NAME" PromptFlowsKeyPath="$KEY_PATH" --stack-name "$STACK_NAME"

