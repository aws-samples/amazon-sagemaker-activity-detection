# Build, Train and Deploy an Activity Detection Model using Amazon SageMaker

In this section,you will build, train and deploy a 3D video classification model on Amazon SageMaker. You will fine-tune a pre-trained model with a ResNet50 backbone by transfer learning on another dataset and test inference on a sample video segment. The pre-trained model from a well-known model zoo reduces the need for large volumes of annotated input videos and can be adapted for tasks in another domain. 
 Once you clone the repository, open the [Jupyter Notebook](./SM-transferlearning-UCF101-Inference.ipynb) and follow the instructions to run the end-to-end SageMaker ML pipeline.
Please make sure that you have the required instance limits for the training phase and endpoint deployment phase. 

