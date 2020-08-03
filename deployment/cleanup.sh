#!/bin/sh 

# This script cleans up all the cloudformation stacks related to the event-detection architecture.

echo "[START] DELETING the event-detection solution..."

read -p "Please STOP the MediaLive Channel first!! If YES, press ENTER to continue..."

read -p "Enter your AWS IAM profile: " profile

account=$(aws sts get-caller-identity --query Account --output text --profile ${profile})
region=$(aws configure get region --profile ${profile})
echo "We will be launching resources in ${region} in account ${account} with AWS CLI Profile ${profile}."

cfn_bucket="CreateInputBucketCFN"
cfn_medialive="CreateMediaLiveCFN"
cfn_lambda="CreateLambdaCFN"
cfn_model="CreateModelCFN"
cfn_dynamodb="CreateDynamoDBCFN"

bucket_input="event-data-bucket-${region}-${account}"
bucket_livestream="event-livestream-bucket-${region}-${account}"

##Separated in different bash file
echo "Cleaning up all the AWS resources used in deploying the architecture..."

echo "Deleting S3 bucket ${bucket_input}..."
aws s3 rb s3://${bucket_input}  --force --profile ${profile}

#echo "Deleting all contents of ${bucket_livestream}..."
aws s3 rb s3://${bucket_livestream} --force --profile ${profile}

read -p "Check if the S3 buckets ${bucket_input} and ${bucket_livestream} are completely Deleted! If YES, press ENTER to continue..."

echo "Deleting the model endpoint stack ${cfn_model}..."
aws cloudformation delete-stack --stack-name ${cfn_model} --profile ${profile}

echo "Deleting the lambda function stack ${cfn_lambda}..."
aws cloudformation delete-stack --stack-name ${cfn_lambda} --profile ${profile}

echo "Deleting the medialive stack ${cfn_medialive}..."
aws cloudformation delete-stack --stack-name ${cfn_medialive} --profile ${profile}

echo "Deleting the dynamodb stack ${cfn_dynamodb}..."
aws cloudformation delete-stack --stack-name ${cfn_dynamodb} --profile ${profile}

echo "Deleting the bucket stack ${cfn_bucket}..."
aws cloudformation delete-stack --stack-name ${cfn_bucket} --profile ${profile}

echo "[SUCCESS] DONE DELETING the event-detection solution!!"
