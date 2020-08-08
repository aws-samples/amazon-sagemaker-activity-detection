#!/bin/sh 

# This script cleans up all the cloudformation stacks related to the activity detection architecture.

echo "[START] DELETING the Activity Detection Solution..."

read -p "Please STOP the MediaLive Channel First!! If YES, press ENTER to continue..."

read -p "Enter your AWS IAM profile: " profile

#AWS Account ID and Region Name
account=$(aws sts get-caller-identity --query Account --output text --profile ${profile})
region=$(aws configure get region --profile ${profile})

#CloudFormation for Input S3 Bucket
cfn_bucket="InputBucketCFN"
#CloudFormation for the Activity Detection Solution 
cfn_activity="ActivityDetectionCFN"

bucket_input="activity-detection-data-bucket-${region}-${account}"
bucket_livestream="activity-detection-livestream-bucket-${region}-${account}"

#Function to wait until a cloudformation is fully created
wait_until_completion()
{
  echo "Waiting for the Deletion of $1..."
  completed=false
  while [ ${completed} = false ]
  do
    sleep 10s
    stack_status=$(aws cloudformation describe-stacks --stack-name $1)
    if [[ -z ${stack_status} ]]; then
      echo "$1 Successfully Deleted!"
      completed=true
    fi
  done
}

echo "Deleting the Input S3 bucket ${bucket_input}..."
aws s3 rb s3://${bucket_input}  --force --profile ${profile}

echo "Deleting the Input Bucket CloudFormation Stack ${cfn_bucket}..."
aws cloudformation delete-stack --stack-name ${cfn_bucket} --profile ${profile}

#Wait until the input bucket cloudformation stack is successfully deleted
wait_until_completion ${cfn_bucket}

echo "Deleting the Livestream S3 bucket ${bucket_livestream}..."
aws s3 rb s3://${bucket_livestream} --force --profile ${profile}

echo "Deleting the Activity Detection CloudFormation Stack ${cfn_activity}..."
aws cloudformation delete-stack --stack-name ${cfn_activity} --profile ${profile}

#Wait until the activity detection cloudformation stack is successfully deleted
wait_until_completion ${cfn_activity}

echo "[SUCCESS] DONE DELETING the Activity Detection Solution!!"