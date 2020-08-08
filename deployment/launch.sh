#!/bin/sh 

# This script creates all the cloudformation stacks related to the activity-detection architecture.

echo "[START] LAUNCHING the Activity Detection Solution using CloudFormation..."

read -p "Enter your AWS IAM profile: " profile

#AWS Account ID and Region Name
account=$(aws sts get-caller-identity --query Account --output text --profile ${profile})
region=$(aws configure get region --profile ${profile})
echo "We will be launching resources in ${region} in account ${account} with AWS CLI Profile ${profile}."

############ [START] PARAMETERS VALUES THAT CAN BE CHANGED #############

#CloudFormation for Input S3 Bucket
cfn_bucket="InputBucketCFN"
#CloudFormation for the Activity Detection Solution 
cfn_activity="ActivityDetectionCFN"

#Input S3 bucket name where all the cloudformation templates and model artifacts are stored
bucket_input="activity-detection-data-bucket"
#S3 path where the templates & model artifacts are saved
s3_data_path="s3://${bucket_input}-${region}-${account}/artifacts/amazon-sagemaker-activity-detection/deployment"

#Bucket name where the video segments from livestream are stored
bucket_livestream="activity-detection-livestream-bucket"

#MediaLive channel name
medialive_channel="activity-detection-channel"
#Medialive input name
medialive_input="activity-detection-input"

#Lambda function name
lambda_name="activity-detection-lambda"

#SageMaker model endpoint name
endpoint_name="activity-detection-endpoint"
#Max number of frames used with the model
model_max_frames=32
#Instance Type (check cfn_model.yaml for the allowed instance types or to make modifications)
instance_type="ml.g4dn.2xlarge"
#Minimum number of Instances
min_instance_count=1
#Maximum number of instances (for autoscaling)
max_instance_count=3

#Dynamo DB table where all the prediction outputs are stored
detection_table_name="activity-detection-table"

############ [END] PARAMETERS VALUES THAT CAN BE CHANGED #############

#Function to wait until a cloudformation is fully created
wait_until_completion()
{
  echo "Waiting for the Creation of $1..."
  completed=false
  while [ ${completed} = false ]
  do
    sleep 10s
    stack_status=$(aws cloudformation describe-stacks --stack-name $1)
    if [[ ${stack_status} == *"CREATE_COMPLETE"* ]]; then
      echo "$1 Successfully Created!"
      completed=true
    elif [[ -z ${stack_status} ]]; then
      echo "Error in Creating $1. Exiting..."
      exit 1
    fi
  done
}

echo "Creating input bucket ${bucket_input}-${region}-${account}..."
aws cloudformation create-stack --stack-name ${cfn_bucket} --template-body file://cloud_formation/cfn_bucket.yaml --parameters  ParameterKey=S3BucketName,ParameterValue=${bucket_input} --profile ${profile}

#Wait until the input bucket & its cloudformation stack is successfully created
wait_until_completion ${cfn_bucket}

echo "Copying source code and data into ${bucket_input}-${region}-${account}..."
#Prepare the files
if [ ! -f PeopleSkiing.mp4 ]; then
    cp ../videos/PeopleSkiing.mp4 .
fi

if [ -f lambda/lambda_function.zip ]; then
    rm lambda/lambda_function.zip
fi
zip lambda/lambda_function.zip -jq lambda/lambda_function.py

if [ -f model/model.tar.gz ]; then
    rm model/model.tar.gz
fi
tar -czf model/model.tar.gz --exclude=".ipynb_checkpoints" -C model/ . 

#Copy all the files into the S3 (exclude ipynb_checkpoints)
#aws s3 cp . ${s3_data_path} --recursive --quiet --exclude "*.ipynb_checkpoints/*"
aws s3 cp "cloud_formation/" "${s3_data_path}/cloud_formation/" --recursive --quiet --exclude "*.ipynb_checkpoints/*"
aws s3 cp "lambda/" "${s3_data_path}/lambda/" --recursive --quiet --exclude "*.ipynb_checkpoints/*"
aws s3 cp "model/" "${s3_data_path}/model/" --recursive --quiet --exclude "*.ipynb_checkpoints/*"
aws s3 cp PeopleSkiing.mp4 "${s3_data_path}/" --quiet

#Remove the extra files from the copy
rm PeopleSkiing.mp4
rm lambda/lambda_function.zip
rm model/model.tar.gz

echo "Launching CloudFormation stack ${cfn_activity}..."
aws cloudformation create-stack --stack-name ${cfn_activity} --template-body file://cloud_formation/cfn_activity_detection.yaml --parameters ParameterKey=InputBucket,ParameterValue=${bucket_input} ParameterKey=DestinationBucket,ParameterValue=${bucket_livestream} ParameterKey=ChannelName,ParameterValue=${medialive_channel}  ParameterKey=InputName,ParameterValue=${medialive_input} ParameterKey=LambdaName,ParameterValue=${lambda_name} ParameterKey=ModelEndpointName,ParameterValue=${endpoint_name} ParameterKey=ModelMaxFrames,ParameterValue=${model_max_frames} ParameterKey=InstanceType,ParameterValue=${instance_type} ParameterKey=MinInstanceCount,ParameterValue=${min_instance_count} ParameterKey=MaxInstanceCount,ParameterValue=${max_instance_count} ParameterKey=DDBTableName,ParameterValue=${detection_table_name} --capabilities CAPABILITY_NAMED_IAM --profile ${profile}

#Wait until the input bucket & its cloudformation stack is successfully created
wait_until_completion ${cfn_activity}

echo "[SUCCESS] DONE CREATING the Activity Detection Solution!! Start the MediaLive Channel to Run it."