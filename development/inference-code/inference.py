# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from __future__ import absolute_import

import subprocess
import sys
import io
import os
import boto3
import time
import json
import uuid

import mxnet as mx
import numpy as np
from mxnet import gluon,nd
from sagemaker_inference import content_types, default_inference_handler, errors
from io import BytesIO
from datetime import datetime


import gluoncv
from gluoncv.data.transforms import video
from gluoncv.data import VideoClsCustom
from gluoncv.utils.filesystem import try_import_decord

ctx = mx.gpu(0) if mx.context.num_gpus() > 0 else mx.cpu()
#UCF101 classes
classes = ['ApplyEyeMakeup'
,'ApplyLipstick'
, 'Archery'
, 'BabyCrawling'
, 'BalanceBeam'
, 'BandMarching'
, 'BaseballPitch'
, 'Basketball'
, 'BasketballDunk'
, 'BenchPress'
, 'Biking'
, 'Billiards'
, 'BlowDryHair'
, 'BlowingCandles'
, 'BodyWeightSquats'
, 'Bowling'
, 'BoxingPunchingBag'
, 'BoxingSpeedBag'
, 'BreastStroke'
, 'BrushingTeeth'
, 'CleanAndJerk'
, 'CliffDiving'
, 'CricketBowling'
, 'CricketShot'
, 'CuttingInKitchen'
, 'Diving'
, 'Drumming'
, 'Fencing'
, 'FieldHockeyPenalty'
, 'FloorGymnastics'
, 'FrisbeeCatch'
, 'FrontCrawl'
, 'GolfSwing'
, 'Haircut'
, 'Hammering'
, 'HammerThrow'
, 'HandstandPushups'
, 'HandstandWalking'
, 'HeadMassage'
, 'HighJump'
, 'HorseRace'
, 'HorseRiding'
, 'HulaHoop'
, 'IceDancing'
, 'JavelinThrow'
, 'JugglingBalls'
, 'JumpingJack'
, 'JumpRope'
, 'Kayaking'
, 'Knitting'
, 'LongJump'
, 'Lunges'
, 'MilitaryParade'
, 'Mixing'
, 'MoppingFloor'
, 'Nunchucks'
, 'ParallelBars'
, 'PizzaTossing'
, 'PlayingCello'
, 'PlayingDaf'
, 'PlayingDhol'
, 'PlayingFlute'
, 'PlayingGuitar'
, 'PlayingPiano'
, 'PlayingSitar'
, 'PlayingTabla'
, 'PlayingViolin'
, 'PoleVault'
, 'PommelHorse'
, 'PullUps'
, 'Punch'
, 'PushUps'
, 'Rafting'
, 'RockClimbingIndoor'
, 'RopeClimbing'
, 'Rowing'
, 'SalsaSpin'
, 'ShavingBeard'
, 'Shotput'
, 'SkateBoarding'
, 'Skiing'
, 'Skijet'
, 'SkyDiving'
, 'SoccerJuggling'
, 'SoccerPenalty'
, 'StillRings'
, 'SumoWrestling'
, 'Surfing'
, 'Swing'
, 'TableTennisShot'
, 'TaiChi'
, 'TennisSwing'
, 'ThrowDiscus'
, 'TrampolineJumping'
, 'Typing'
, 'UnevenBars'
, 'VolleyballSpiking'
, 'WalkingWithDog'
, 'WallPushups'
, 'WritingOnBoard'
, 'YoYo']
dict_classes = dict(zip(range(len(classes)), classes))
# ------------------------------------------------------------ #
# Hosting methods                                              #
# ------------------------------------------------------------ #

def model_fn(model_dir):
    print('here')
    print(ctx)
    symbol = mx.sym.load('%s/model-symbol.json' % model_dir)
    outputs = mx.symbol.softmax(data=symbol, name='softmax_label')
    inputs = mx.sym.var('data')
    net = gluon.SymbolBlock(outputs, inputs)
    net.load_parameters('%s/model-0000.params' % model_dir, ctx=ctx)
    return net

#transform function that uses json (s3 path) as input and output
def transform_fn(net, data, input_content_type, output_content_type):
    print('transform_fn here')
    start = time.time()
    data = json.loads(data)
    video_data = read_video_data(data['S3_VIDEO_PATH'])
    print(time.time())
    video_input = video_data.as_in_context(ctx)
    probs = net(video_input.astype('float32', copy=False))
    print(time.time())
    predicted = mx.nd.argmax(probs, axis=1).asnumpy().tolist()[0]
    probability = mx.nd.max(probs, axis=1).asnumpy().tolist()[0]
     
    probability = '{:.4f}'.format(probability)
    predicted_name = dict_classes[int(predicted)]
    total_prediction = time.time()-start
    total_prediction = '{:.4f}'.format(total_prediction)
    print(probability)
    print(predicted_name)
    print('Model prediction time: ', total_prediction)
    
    now = datetime.utcnow()
    time_format = '%Y-%m-%d %H:%M:%S %Z%z'
    now = now.strftime(time_format)

    response = {
        'S3Path': {'S': data['S3_VIDEO_PATH']},
        'Predicted': {'S': predicted_name},
        'Probability': {'S': probability},
        'DateCreatedUTC': {'S': now},
    }

    return json.dumps(response), output_content_type

def get_bucket_and_key(s3_path):
    """Get the bucket name and key from the given path.
    Args:
        s3_path(str): Input S3 path
    """
    s3_path = s3_path.replace('s3://', '')
    s3_path = s3_path.replace('S3://', '') #Both cases
    bucket, key = s3_path.split('/', 1)
    return bucket, key



def read_video_data(s3_video_path, num_frames=32):
    """Read and preprocess video data from the S3 bucket."""
    print('read and preprocess video data here ')
    s3_client = boto3.client('s3')
    #print(uuid.uuid4())
    fname = s3_video_path.replace('s3://', '')
    fname = fname.replace('S3://', '')
    fname = fname.replace('/', '')
    #download_path = '/tmp/{}-{}'.format(uuid.uuid4(), fname)
    #video_list_path = '/tmp/{}-{}'.format(uuid.uuid4(), 'video_list.txt')
    download_path = '/tmp/' + fname
    video_list_path = '/tmp/video_list' + str(uuid.uuid4()) + '.txt' 
    bucket, key = get_bucket_and_key(s3_video_path)
    s3_client.download_file(bucket, key, download_path)
    
    #update download_path filename to be unique
    filename,ext = os.path.splitext(download_path)    # save the file extension
    filename = filename + str(uuid.uuid4())
    os.rename(download_path, filename+ext)
    download_path = filename+ext
    
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
        
    #The transformation function does three things: center crop the image to 224x224 in size, transpose it to num_channels,num_frames,height*width, and normalize with mean and standard deviation calculated across all ImageNet images.

    #Use the general gluoncv dataloader VideoClsCustom to load the data with num_frames = 32 as the length.
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
    #os.system('rm {}'.format(download_path))
    #os.system('rm {}'.format(video_list_path))

    return clip_input


