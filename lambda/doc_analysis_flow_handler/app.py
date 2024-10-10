import json
import boto3
from datetime import datetime
import os
import logging
from typing import Dict
from typing import Optional
import traceback

OUTPUT_BUCKET_NAME = os.environ['OUTPUT_BUCKET_NAME']
QUEUE_URL = os.environ['QUEUE_URL']

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
s3 = boto3.client('s3')
sqs = boto3.client('sqs')
bedrock_agent = boto3.client('bedrock-agent-runtime')


def lambda_handler(sqs_event: Dict, context) -> bool:
	"""
	Lambda function handler for processing SQS events.

	Args:
		sqs_event (Dict): The SQS event data.
		context: The Lambda context object.

	Returns:
		bool: True if the function executed successfully, False otherwise.
	"""
	logger.info(f"Processing event: {json.dumps(sqs_event)}")
	try:
		validate_sqs_event(sqs_event)
		previous_result = extract_previous_result(sqs_event)
		case_id = previous_result["case_id"]
		document_manifest = previous_result["documents"]

		for document in document_manifest:
			process_document(document, case_id)

		delete_sqs_message(sqs_event)
		return True
	except Exception as e:
		logger.error(f"Error processing SQS event: {e}")
		logger.info(traceback.format_exc())
		return False

def save_to_s3(content: str, bucket_name: str, file_key: str) -> Optional[str]:
    """
    Save a string content to an Amazon S3 bucket with a specified file key.

    Args:
        content (str): The content to be saved.
        bucket_name (str): The name of the S3 bucket.
        file_key (str): The file key (path) for the object in S3.

    Returns:
        Optional[str]: The file key if the operation is successful, None otherwise.
    """
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=content.encode('utf-8')
        )
        logger.info(f"Successfully saved content to S3 bucket '{bucket_name}' with key '{file_key}'")
        return file_key
    except Exception as e:
        logger.error(f"Error saving content to S3: {e}")
        return None

def validate_sqs_event(sqs_event: Dict):
	"""
	Validate the SQS event data.

	Args:
		sqs_event (Dict): The SQS event data.

	Raises:
		Exception: If the SQS event data is invalid.
	"""
	if "Records" not in sqs_event:
		raise Exception("No Records section")
	if len(sqs_event["Records"]) != 1:
		raise Exception("Expected only 1 record")

def extract_previous_result(sqs_event: Dict) -> Dict:
	"""
	Extract the previous result from the SQS event data.

	Args:
		sqs_event (Dict): The SQS event data.

	Returns:
		Dict: The previous result data.
	"""
	body = sqs_event["Records"][0]["body"]
	return json.loads(body)

def process_document(document: Dict, case_id: str):
	"""
	Process a document by invoking the Bedrock prompt flow and saving the result to S3.

	Args:
		document (Dict): The document data.
		case_id (str): The case ID.
	"""
	flow_id = document["run_flow_id"]
	flow_alias_id = document["run_flow_alias"]
	directory, f = os.path.split(document['doc_text_s3key'])
	report_s3key = os.path.join(directory,"report.txt")

	document["todays_date"] = datetime.now().strftime("%Y-%m-%d")
	document["case_id"] = case_id

	result = invoke_bedrock_flow(flow_id, flow_alias_id, document)

	outcome = process_bedrock_result(result)
	save_to_s3(outcome, OUTPUT_BUCKET_NAME, report_s3key)

def delete_sqs_message(sqs_event: Dict):
	"""
	Delete the SQS message from the queue.

	Args:
		sqs_event (Dict): The SQS event data.
	"""
	receipt_handle = sqs_event["Records"][0]["receiptHandle"]
	sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)

def invoke_bedrock_flow(flow_id: str, flow_alias_id: str, document: Dict) -> Dict:
	"""
	Invoke the Bedrock prompt flow.

	Args:
		flow_id (str): The flow ID.
		flow_alias_id (str): The flow alias ID.
		document (Dict): The document data.

	Returns:
		Dict: The Bedrock response.
	"""
	response = bedrock_agent.invoke_flow(
		flowIdentifier=flow_id,
		flowAliasIdentifier=flow_alias_id,
		inputs=[
			{
				"content": {
					"document": document
				},
				"nodeName": "FlowInputNode",
				"nodeOutputName": "document"
			}
		]
	)
	
	result = {}
	for event in response.get("responseStream"):
		result.update(event)
	return result

def process_bedrock_result(result):
	"""
	Process the Bedrock result and return the outcome.

	Args:
		result: The Bedrock response.

	Returns:
		str: The outcome of the Bedrock result.
	"""
	outcome = ""

	if result['flowCompletionEvent']['completionReason'] == 'SUCCESS':
		logger.info("Prompt flow invocation was successful! The output of the prompt flow is as follows:\n")
		outcome += result['flowOutputEvent']['content']['document']
	
	
	else:
		logger.info("The prompt flow invocation completed because of the following reason:", result['flowCompletionEvent']['completionReason'])
		outcome += result['flowCompletionEvent']['completionReason']
	return outcome