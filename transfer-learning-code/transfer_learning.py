# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from __future__ import print_function

import argparse
import logging
import os
import numpy as np
import json
import time

import mxnet as mx
from mxnet import gluon
from mxnet.gluon import nn
from mxnet import autograd as ag
from mxnet.gluon.data.vision import transforms

import gluoncv as gcv
from gluoncv.data.transforms import video
from gluoncv.data import VideoClsCustom
from gluoncv.model_zoo import get_model
from gluoncv.utils import makedirs, LRSequential, LRScheduler, split_and_load, TrainingHistory

logging.basicConfig(level=logging.DEBUG)

# ------------------------------------------------------------ #
# Training methods                                             #
# ------------------------------------------------------------ #


def train(args):
    # SageMaker passes num_cpus, num_gpus and other args we can use to tailor training to
    # the current container environment
    num_gpus = mx.context.num_gpus()
    ctx = [mx.gpu(i) for i in range(num_gpus)] if num_gpus > 0 else [mx.cpu()]
    # retrieve the hyperparameters we set in notebook (with some defaults)
    
    #number of training examples utilized in one iteration.
    batch_size = args.batch_size
    #number of times an entire dataset is passed forward and backward through the neural network 
    epochs = args.epochs
    #tuning parameter in an optimization algorithm that determines the step size at each iteration while moving toward a   minimum of a loss function.
    learning_rate = args.learning_rate
    #Momentum remembers the update Δ w at each iteration, and determines the next update as a linear combination of the gradient and the previous update
    momentum = args.momentum
    #Optimizers are algorithms or methods used to change the attributes of your neural network such as weights and learning rate in order to reduce the losses. 
    optimizer = args.optimizer
    #after each update, the weights are multiplied by a factor slightly less than 1.
    wd = args.wd
    optimizer_params = {'learning_rate': learning_rate, 'wd': wd, 'momentum': momentum}
    log_interval = args.log_interval
    
    #In this example, we use Inflated 3D model (I3D) with ResNet50 backbone trained on Kinetics400 dataset. We want to replace the last classification (dense) layer to the number of classes in the dataset. 
    model_name = 'i3d_resnet50_v1_custom'
    #number of classes in the dataset
    nclass = 101
    #number of workers for the data loader
    num_workers = 8
    
    current_host = args.current_host
    hosts = args.hosts
    model_dir = args.model_dir
    CHECKPOINTS_DIR = '/opt/ml/checkpoints'
    checkpoints_enabled = os.path.exists(CHECKPOINTS_DIR)

    data_dir = args.train
    segments = 'rawframes'
    train ='ucfTrainTestlist/ucf101_train_split_2_rawframes.txt'
    
    #load the data with data loader
    train_data = load_data(data_dir,batch_size,num_workers,segments,train)
    # define the network
    net = define_network(ctx,model_name,nclass)
    #define the gluon trainer
    trainer = gluon.Trainer(net.collect_params(), optimizer, optimizer_params)
    #define loss function
    loss_fn = gluon.loss.SoftmaxCrossEntropyLoss()
    #define training metric
    train_metric = mx.metric.Accuracy()
    train_history = TrainingHistory(['training-acc'])
    net.hybridize()
    #learning rate decay hyperparameters
    lr_decay_count = 0
    lr_decay = 0.1
    lr_decay_epoch = [40, 80, 100]
    for epoch in range(epochs):
        tic = time.time()
        train_metric.reset()
        train_loss = 0

        # Learning rate decay
        if epoch == lr_decay_epoch[lr_decay_count]:
            trainer.set_learning_rate(trainer.learning_rate*lr_decay)
            lr_decay_count += 1

        # Loop through each batch of training data
        for i, batch in enumerate(train_data):
            # Extract data and label
            data = split_and_load(batch[0], ctx_list=ctx, batch_axis=0,even_split=False)
            label = split_and_load(batch[1], ctx_list=ctx, batch_axis=0,even_split=False)

            # AutoGrad
            with ag.record():
                output = []
                for _, X in enumerate(data):
                    X = X.reshape((-1,) + X.shape[2:])
                    pred = net(X)
                    output.append(pred)
                loss = [loss_fn(yhat, y) for yhat, y in zip(output, label)]

            # Backpropagation
            for l in loss:
                l.backward()

            # Optimize
            trainer.step(batch_size)

            # Update metrics
            train_loss += sum([l.mean().asscalar() for l in loss])
            train_metric.update(label, output)

            if i == 100:
                break

        name, acc = train_metric.get()

        # Update history and print metrics
        train_history.update([acc])
        print('[Epoch %d] train=%f loss=%f time: %f' %
            (epoch, acc, train_loss / (i+1), time.time()-tic))

    print('saving the model')
    save(net, model_dir)
     
def save(net, model_dir):
    # save the model
    net.export('%s/model'% model_dir)


def define_network(ctx,model_name,nclass):
    #In GluonCV, we can get a customized model with one line of code.
    net = get_model(name=model_name, nclass=nclass)
    net.collect_params().reset_ctx(ctx)
    print(net)
    return net


def load_data(data_dir, batch_size,num_workers,segments,train):

    #The transformation function does three things: center crop the image to 224x224 in size, transpose it to num_channels,num_frames,height*width, and normalize with mean and standard deviation calculated across all ImageNet images.

    #Use the general gluoncv dataloader VideoClsCustom to load the data with num_frames = 32 as the length. For another  dataset, you can just replace the value of root and setting to your data directory and your prepared text file.
    
    transform_train = video.VideoGroupTrainTransform(size=(224, 224), scale_ratios=[1.0, 0.8], mean=[0.485, 0.456, 0.406], 
                                                          std=[0.229, 0.224, 0.225])
    train_dataset = VideoClsCustom(root=data_dir + '/' + 
                                   segments,setting=data_dir + '/' + train,train=True,new_length=32,transform=transform_train)
    print(os.listdir(data_dir+ '/' + segments))
    print('Load %d training samples.' % len(train_dataset))
    return gluon.data.DataLoader(train_dataset, batch_size=batch_size,
                                                   shuffle=True, num_workers=num_workers)



# ------------------------------------------------------------ #
# Training execution                                           #
# ------------------------------------------------------------ #

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--learning-rate', type=float, default=0.001)
    parser.add_argument('--momentum', type=float, default=0.9)
    parser.add_argument('--wd', type=float, default=0.0001)
    parser.add_argument('--log-interval', type=float, default=100)

    parser.add_argument('--optimizer', type=str, default='sgd')
    parser.add_argument('--model-dir', type=str, default=os.environ['SM_MODEL_DIR'])
    parser.add_argument('--train', type=str, default=os.environ['SM_CHANNEL_TRAINING'])

    parser.add_argument('--current-host', type=str, default=os.environ['SM_CURRENT_HOST'])
    parser.add_argument('--hosts', type=list, default=json.loads(os.environ['SM_HOSTS']))

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    train(args)