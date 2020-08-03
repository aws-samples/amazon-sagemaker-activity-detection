#!/bin/sh 

# This script creates all the cloudformation stacks related to the event-detection architecture.

echo "[START] LAUNCHING the event-detection solution..."

read -p "Enter your AWS IAM profile: " profile

account=$(aws sts get-caller-identity --query Account --output text --profile ${profile})
region=$(aws configure get region --profile ${profile})
echo "We will be launching resources in ${region} in account ${account} with AWS CLI Profile ${profile}."

cfn_bucket="CreateInputBucketCFN"
cfn_medialive="CreateMediaLiveCFN"
cfn_lambda="CreateLambdaCFN"
cfn_model="CreateModelCFN"
cfn_dynamodb="CreateDynamoDBCFN"

bucket_input="event-data-bucket"
bucket_livestream="event-livestream-bucket"

medialive_channel="event-detection-channel"
medialive_input="event-detection-input"

lambda_name="event-detection-lambda"

detection_table_name="event-detection-table"

endpoint_name="event-detection-endpoint"
model_max_frames=32

s3_data_path="s3://${bucket_input}-${region}-${account}/event-detection/deployment/"
echo "Creating input bucket ${bucket_input}-${region}-${account}..."
aws cloudformation create-stack --stack-name ${cfn_bucket} --template-body file://cloud_formation/cfn_bucket.yaml --parameters  ParameterKey=S3BucketName,ParameterValue=${bucket_input} --profile ${profile}

read -p "Check if the stack ${cfn_bucket} is complete! If YES, press ENTER to continue..."

echo "Copying source code and data into ${bucket_input}-${region}-${account}..."

#Prepare the files
if [ ! -f PeopleSkiing.mp4 ]; then
    cp ../PeopleSkiing.mp4 .

if [ -f lambda/lambda_function.zip ]; then
    rm lambda/lambda_function.zip
fi
zip lambda/lambda_function.zip -j lambda/lambda_function.py

if [ -f model/model.tar.gz ]; then
    rm model/model.tar.gz
fi
tar -czvf model/model.tar.gz -C model/ . 

#Copy all the files into the S3
aws s3 cp --recursive . "${s3_data_path}"

#Remove the extra files from the copy
rm PeopleSkiing.mp4
rm lambda/lambda_function.zip
rm model/model.tar.gz

echo "Creating the lambda function ${lambda_name} ..."
aws cloudformation create-stack --stack-name ${cfn_lambda} --template-body file://cloud_formation/cfn_lambda.yaml --parameters ParameterKey=LambdaName,ParameterValue=${lambda_name} ParameterKey=TriggerBucketName,ParameterValue=${bucket_livestream} ParameterKey=LambdaCodeBucket,ParameterValue=${bucket_input} ParameterKey=DetectionTableName,ParameterValue=${detection_table_name} ParameterKey=EndpointName,ParameterValue=${endpoint_name} ParameterKey=ModelMaxFrames,ParameterValue=${model_max_frames} --capabilities CAPABILITY_NAMED_IAM --profile ${profile}

echo "Creating the Elemental MediaLive channel ${medialive_channel} ..."
aws cloudformation create-stack --stack-name ${cfn_medialive} --template-body file://cloud_formation/cfn_medialive.yaml --parameters ParameterKey=ChannelName,ParameterValue=${medialive_channel} ParameterKey=InputName,ParameterValue=${medialive_input} ParameterKey=InputVideoBucket,ParameterValue=${bucket_input} ParameterKey=DestinationBucket,ParameterValue=${bucket_livestream} --capabilities CAPABILITY_NAMED_IAM --profile ${profile}

echo "Creating the model endpoint ${endpoint_name} ..."
aws cloudformation create-stack --stack-name ${cfn_model} --template-body file://cloud_formation/cfn_model.yaml --parameters ParameterKey=ModelEndpointName,ParameterValue=${endpoint_name} ParameterKey=ModelDataBucket,ParameterValue=${bucket_input} --capabilities CAPABILITY_NAMED_IAM --profile ${profile}

echo "Creating the dynamodb table ${detection_table_name} ..."
aws cloudformation create-stack --stack-name ${cfn_dynamodb} --template-body file://cloud_formation/cfn_dynamodb.yaml --parameters ParameterKey=DDBTableName,ParameterValue=${detection_table_name} --profile ${profile}

echo "[SUCCESS] DONE BUILDING the event-detection solution!! Please check if all the CloudFormation stacks are successfully created."
