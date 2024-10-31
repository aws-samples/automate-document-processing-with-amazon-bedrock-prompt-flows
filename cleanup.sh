#!/bin/bash
set -eo pipefail
STACK_NAME=document-processing-bedrock-prompt-flows
ACCOUNT_NUMBER=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="$STACK_NAME"-"$ACCOUNT_NUMBER"

# Attempt to get bucket names from CloudFormation outputs
if ! SOURCE_BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`SourceS3Bucket`].OutputValue' --output text 2>/dev/null); then
    echo "Warning: Could not retrieve SOURCE_BUCKET from stack $STACK_NAME"
else
    # Only attempt to remove if we got a non-empty bucket name
    if [ -n "$SOURCE_BUCKET" ] && [ "$SOURCE_BUCKET" != "None" ]; then
        aws s3 rm "s3://$SOURCE_BUCKET" --recursive
    fi
fi

if ! DEST_BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`DestinationS3Bucket`].OutputValue' --output text 2>/dev/null); then
    echo "Warning: Could not retrieve DEST_BUCKET from stack $STACK_NAME"
else
    # Only attempt to remove if we got a non-empty bucket name
    if [ -n "$DEST_BUCKET" ] && [ "$DEST_BUCKET" != "None" ]; then
        aws s3 rm "s3://$DEST_BUCKET" --recursive
    fi
fi


#FUNCTION=$(aws cloudformation describe-stack-resource --stack-name "$STACK_NAME" --logical-resource-id function --output text)
#echo $FUNCTION
sam delete --s3-bucket "$BUCKET_NAME" --stack-name "$STACK_NAME"


