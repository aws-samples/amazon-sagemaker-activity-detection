# Using Amazon SageMaker for Activity Detection on a Live Video Stream

This code repository contains two parts:

1. [Development](./development): It contains a Jupyter Notebook and its associated python source code to build, train and deploy an activity detection model using Amazon SageMaker. Transfer learning is used to fine-tune an MXNet-based pretrained 3D video classification model with another dataset.

2. [Deployment](./deployment): It contains CloudFormation templates and other resources to deploy an end-to-end activity detection solution using CloudFormation

A blog post associated with the code repository is found [here](https://aws.amazon.com/blogs/machine-learning/using-amazon-sagemaker-for-activity-detection-on-a-live-video-stream/).

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
