# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import boto3
import time
import subprocess


ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
MODEL_MAX_FRAMES = os.environ['MODEL_MAX_FRAMES']
DETECTION_TABLE_NAME = os.environ['DETECTION_TABLE_NAME']

sage_client = boto3.client('runtime.sagemaker')
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    response = ''
    for record in event['Records']:
        bucket_in = record['s3']['bucket']['name']
        key_in = record['s3']['object']['key']
        s3_video_path = os.path.join('s3://' + bucket_in, key_in)
        prefix, infile = key_in.split('/', 1)
        s3_client.download_file(bucket_in, key_in,'/tmp/'+infile)
        print('input:', s3_video_path)
        subprocess.run(['rm', '/tmp/'+infile])

        data = {}
        data['S3_VIDEO_PATH'] = s3_video_path
        data['MODEL_MAX_FRAMES'] = int(MODEL_MAX_FRAMES)
        data['DETECTION_TABLE_NAME'] = DETECTION_TABLE_NAME

        response = sage_client.invoke_endpoint(EndpointName=ENDPOINT_NAME,
                                              Body=json.dumps(data))
        response = json.loads(response['Body'].read().decode('utf-8'))
    return response