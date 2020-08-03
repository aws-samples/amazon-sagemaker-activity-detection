from __future__ import print_function

import json
import uuid
import boto3
import time

import mxnet as mx
from mxnet import gluon, nd
import numpy as np

from gluoncv.data.transforms import video
from gluoncv.data import VideoClsCustom
from gluoncv.utils.filesystem import try_import_decord

import multiprocessing as mp
import cv2
import re
import pandas as pd
import os

from datetime import datetime

TIME_FORMAT = '%Y-%m-%d %H:%M:%S %Z%z'
CLASSES_PATH = '/opt/ml/model/classes.txt'

def model_fn(model_dir):
    """
    Load the gluon model. Called once when hosting service starts.

    :param: model_dir The directory where model files are stored.
    :return: a model (in this case a Gluon network)
    """
    symbol = mx.sym.load('%s/model-symbol.json' % model_dir)
    outputs = mx.symbol.softmax(data=symbol, name='softmax_label')
    inputs = mx.sym.var('data')
    net = gluon.SymbolBlock(outputs, inputs)
    ctx = mx.gpu() if mx.context.num_gpus() else mx.cpu()
    net.load_parameters('%s/model-0000.params' % model_dir, ctx=ctx)
    return net


def transform_fn(net, data,input_content_type, output_content_type):
    """
    Transform a request using the Gluon model. Called once per request.

    :param net: The Gluon model.
    :param data: The request payload.
    :param input_content_type: The request content type.
    :param output_content_type: The (desired) response content type.
    :return: response payload and content type.
    """
    # we can use content types to vary input/output handling, but
    # here we just assume json for both
    data = json.loads(data)
    
    classes = read_classes(CLASSES_PATH)
    dict_classes = dict(zip(range(len(classes)), classes))
    
    start = time.time()
    video_data = read_video_data(data['S3_VIDEO_PATH'], data['MODEL_MAX_FRAMES'])
    print('Loading video time={}'.format(time.time()-start))
    
    ctx = mx.gpu() if mx.context.num_gpus() else mx.cpu()
    video_input = video_data.as_in_context(ctx)
    
    start = time.time()
    probs = net(video_input.astype('float32', copy=False))
    print('Getting predictions time={}'.format(time.time()-start))
    
    start = time.time()
    predicted = mx.nd.argmax(probs, axis=1).asnumpy().tolist()[0]
    probability = mx.nd.max(probs, axis=1).asnumpy().tolist()[0]
    print('Getting predicted class & its probability time='.format(time.time()-start))
    
    probability = '{:.4f}'.format(probability)
    predicted_name = dict_classes[int(predicted)]

    now = datetime.utcnow()
    now = now.strftime(TIME_FORMAT)

    response = {
        'S3Path': {'S': data['S3_VIDEO_PATH']},
        'Predicted': {'S': predicted_name},
        'Probability': {'S': probability},
        'DateCreatedUTC': {'S': now},     
    }

    start = time.time()
    response = save_to_dynamodb(response, data['DETECTION_TABLE_NAME'])
    print('Saving to dynamoDB time='.format(time.time()-start))

    response_body = json.dumps(response)
    return response_body, output_content_type


def get_bucket_and_key(s3_path):
    """Get the bucket name and key from the given path.
    Args:
        s3_path(str): Input S3 path
    """
    s3_path = s3_path.replace('s3://', '')
    s3_path = s3_path.replace('S3://', '') #Both cases
    bucket, key = s3_path.split('/', 1)
    return bucket, key


def read_classes(classes_path='classes.txt'):
    """Load list of classes from local txt file."""
    with open(classes_path, 'r') as fopen:
        classes = fopen.readlines()
    classes = [clas.strip() for clas in classes]
    return classes

    
def read_video_data(s3_video_path, num_frames=32):
    """Read and preprocess video data from the S3 bucket."""
    
    s3_client = boto3.client('s3')
    
    fname = s3_video_path.replace('s3://', '')
    fname = fname.replace('S3://', '')
    fname = fname.replace('/', '')
    download_path = '/tmp/{}-{}'.format(uuid.uuid4(), fname)
    video_list_path = '/tmp/{}-{}'.format(uuid.uuid4(), 'video_list.txt')
    
    bucket, key = get_bucket_and_key(s3_video_path)
    s3_client.download_file(bucket, key, download_path)
    
    #Dummy duration and label with each video path
    video_list = '{} {} {}'.format(download_path, 10, 1)
    with open(video_list_path, 'w') as fopen:
        fopen.write(video_list)

    #Constants
    data_dir = '/tmp/'
    num_segments = 1
    new_length = num_frames
    new_step =1
    use_decord = True
    video_loader = True
    slowfast = False
    #Preprocessing params
    input_size = 224
    mean = [0.485, 0.456, 0.406]
    std=[0.229, 0.224, 0.225]

    transform = video.VideoGroupValTransform(size=input_size, mean=mean, std=std)
    video_utils = VideoClsCustom(root=data_dir,
                                 setting=video_list_path,
                                 num_segments=num_segments,
                                 new_length=new_length,
                                 new_step=new_step,
                                 video_loader=video_loader,
                                 use_decord=use_decord,
                                 slowfast=slowfast)
    
    #Read for the video list
    video_name = video_list.split()[0]

    decord = try_import_decord()
    decord_vr = decord.VideoReader(video_name)
    duration = len(decord_vr)

    skip_length = new_length * new_step
    segment_indices, skip_offsets = video_utils._sample_test_indices(duration)

    if video_loader:
        if slowfast:
            clip_input = video_utils._video_TSN_decord_slowfast_loader(video_name, decord_vr, 
                                                                       duration, segment_indices, skip_offsets)
        else:
            clip_input = video_utils._video_TSN_decord_batch_loader(video_name, decord_vr, 
                                                                    duration, segment_indices, skip_offsets)
    else:
        raise RuntimeError('We only support video-based inference.')

    clip_input = transform(clip_input)

    if slowfast:
        sparse_sampels = len(clip_input) // (num_segments * num_crop)
        clip_input = np.stack(clip_input, axis=0)
        clip_input = clip_input.reshape((-1,) + (sparse_sampels, 3, input_size, input_size))
        clip_input = np.transpose(clip_input, (0, 2, 1, 3, 4))
    else:
        clip_input = np.stack(clip_input, axis=0)
        clip_input = clip_input.reshape((-1,) + (new_length, 3, input_size, input_size))
        clip_input = np.transpose(clip_input, (0, 2, 1, 3, 4))

    if new_length == 1:
        clip_input = np.squeeze(clip_input, axis=2)    # this is for 2D input case

    clip_input = nd.array(clip_input)
    
    #Cleanup temp files
    os.remove(download_path)
    os.remove(video_list_path)

    return clip_input


def table_exists(dynamodb, table_name):
    """
    Checks if dynamoDB table exists.
    Args:
        dynamodb(boto3.client): DynamoDB Boto3 Client object
        table_name(str): Table name
    Returns:
        True if exists otherwise False
    """
    response = dynamodb.list_tables()
    if table_name in response['TableNames']:
        return True
    return False


def create_table(dynamodb, table_name, key_schema, attribute_defs):
    """
    Creates a new dynamoDB table if not exists.
    Args:
        dynamodb(boto3.client): DynamoDB Boto3 Client object
        table_name(str): Table name
        key_schema(dict): Key schema of the table
        attribute_defs(dict): Attribute definitions
    Returns:
        Status of the created table
    """

    if not table_exists(dynamodb, table_name):
        response = dynamodb.create_table(
            TableName=table_name,
            KeySchema=key_schema,
            AttributeDefinitions=attribute_defs,
            BillingMode='PAY_PER_REQUEST'
        )
        status = response['TableDescription']['TableStatus']
        while(status != 'ACTIVE'):
            time.sleep(3)
            response = dynamodb.describe_table(TableName=table_name)
            status = response['Table']['TableStatus']
        return status
            
        
def save_to_dynamodb(item, table_name):
    """
    Adds a record to a dynamodb table. It creates the table if not existing.
    Args:
        item(dict): Record to be added
        table_name(str): Table name
    Returns:
        Success/fail response message
    """
    dynamodb = boto3.client('dynamodb')
    
    exists = table_exists(dynamodb, table_name)
    if not exists:
        KEY_SCHEMA = [
            {
                'AttributeName': 'S3Path',
                'KeyType': 'HASH'  #Partition key
            }]

        ATTRIBUTE_DEFS=[
            {
                'AttributeName': 'S3Path',
                'AttributeType': 'S'
            }]
        create_table(dynamodb, table_name, KEY_SCHEMA, ATTRIBUTE_DEFS)
        
    response = dynamodb.put_item(TableName=table_name, Item=item)
    status_code = response['ResponseMetadata']['HTTPStatusCode']
    response = {'StatusCode': status_code}
    if status_code==200:
        response['Message'] = 'Success'
    else:
        response['Message'] = 'Fail'
    return response