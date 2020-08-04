# Using Amazon SageMaker for ML Inference on Video Livestream

This is an AWS-based machine learning solution to detect activity in a video segment from a live stream. A 3D video classification network [I3D gluoncv](https://gluon-cv.mxnet.io/model_zoo/action_recognition.html) model with ResNet50_v1 backbone and pretrained on [Kinetics400](https://deepmind.com/research/open-source/kinetics) dataset was used to fine-tune it with [UCF101](https://www.crcv.ucf.edu/data/UCF101.php) action recognition dataset. Apache MXNet has been chosen as the deep learning framework here because of the availability of the GluonCV toolkit. The  [GluonCV](https://gluon-cv.mxnet.io/contents.html) model was converted to symbolic format as shown [here](https://medium.com/@julsimon/quick-tip-converting-gluon-models-to-symbolic-format-9513e5dd1d73). The converted and compressed model is included in this repo. Any similar model that is retrained on other custom datasets can also be used here. The model will be deployed on Amazon SageMaker endpoint to run inference on an incoming live video stream generated in a continuous loop. The inference payload will be a S3 object pointer to the video segment. The use of S3 pointer eliminates the need to serialize and deserialize a large video frame payload over REST API. The endpoint inference will include frame sampling and pre-processing followed by video segment classification. In this setup, an AWS Elemental Medialive channel is created based on the sample video included here. This is mainly used to demonstrate the solution with video livestream but any other livestream setup can also be used. The following example shows you how to setup the solution in your AWS Account in the us-west-2 Region.

The structure of the repository is as follows : 

1) Development notebook with custom data prep, training and inference script with SageMaker MXNet framework

2) Deployment solution with cloud formation 

The following diagram illustrates the AWS services used to implement the solution.

![Architecture of the Solution](images/architecture.png)

The workflow works as follows:

1. AWS Elemental MediaLive sends live video with HTTP Live Streaming (HLS) and regularly generates fragments of equal length (10 seconds) as .ts files and an index file that contains references of the fragmented files as a .m3u8 file in a S3 bucket.

2. An upload of each video .ts fragment into the S3 bucket triggers a lambda function.

3. The lambda function simply invokes a SageMaker endpoint for activity detection with the S3 pointer as a payload input.

4. The endpoint internally triggers a SageMaker Inference Pipeline and writes the video classification output to Amazon DynamoDB.

## Prerequisites

1. Ensure that AWS CLI is installed. If not, please install by following [this](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html).

2. Ensure you have your AWS CLI Profile setup. If not, do as follows. In this example, the profile name is `detector` but feel free to use any name:

![AWS IAM Profile](images/profile.png)

## Deploying the Solution

NOTE: There is a cost associated with the deployment and running of the solution. Please remember to delete all the AWS CloudFormation stacks when you are done with it to avoid additional charges. The steps to delete it is given in the next section.

To deploy the solution, we prepared `launch.sh` that provides a step-by-step commands and instructions. Run the bash file and follow the given instructions. All the AWS services are created by using [CloudFormation Stacks](https://console.aws.amazon.com/cloudformation/). After you create a stack at each step, please make sure it is successfully created by going to the [CloudFormation Console](https://console.aws.amazon.com/cloudformation/). After it is successfully created, press `ENTER` in the commandline to continue. Note that, at the beginning, it will ask you to provide the profile name. Please provide the name you created in the previous section.

Before running `launch.sh`, ensure that is is executable. Run the following commands:

```bash
chmod +x launch.sh
./launch.sh
```

![Launching](images/launch.png)

Once you successfully run the `launch.sh`, you will be able to create all the AWS resources used in the solution. When you go to your [CloudFormation Console](https://console.aws.amazon.com/cloudformation/), you will see all the stacks that are successfully created. You should get the same as shown below:

![CloudFormation Stacks](images/stacks.png)

If you get all the stacks created with status `CREATE_COMPLETE`, CONGRATULATIONS!! You have successfully deployed the end-to-end solution.

## Using the Solution

After the solution is deployed, it is time to run it and see its outputs.

1. First go to the [AWS Elemental Medialive Console](https://console.aws.amazon.com/medialive/) and start the channel for live-streaming as shown below. Please wait for the channel state to change to `Running`.

![MediaLive Channel](images/medialive.png)

2. Once the channel state is changed to `Running`, ts-formatted video segments will be saved into the the livestream [S3 bucket](https://console.aws.amazon.com/s3/) as follows:

![TS-Formatted Videos](images/s3_ts.png)

3. Each ts-formatted video upload will trigger a lambda function. The lambda function invokes a SageMaker endpoint for activity detection with the S3 pointer as a payload input. The deployed model predicts the event and saves the results into a [DynamoDB table](https://console.aws.amazon.com/dynamodb/) as shown below:

![DynamoDB Table](images/dynamodb.png)

## Deleting the Solution

If you no longer need the solution, it can be deleted by running `cleanup.sh` script. Before you start running the script, please stop the AWS Elemental MediaLive channel by going to the [MediaLive Console](https://console.aws.amazon.com/medialive/). Once you start it, please follow the instructions. Run the commands below to start cleaning up the AWS services used in the solution:

```bash
chmod +x cleanup.sh
./cleanup.sh
```

![Deleting AWS Resources](images/cleanup.png)

Once you ran the script successfully, please go to your [CloudFormation Console](https://console.aws.amazon.com/cloudformation/) and make sure that all the created stacks are deleted properly. If so, CONGRATULATIONS!! You have successfully deleted all the AWS resources associated with the solution.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.