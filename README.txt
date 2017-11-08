Description: 

Python Rest API to manage Elastic LoadBalancer on AWS

Details:

The API was developed with python3, modules used: Flask, flask_basicauth and boto3.
Three main http methods are in place:
GET http://hostname/elb/{elbName} - List all EC2 Instances currently attached to the elb specified
POST http://hostname/elb/{elbName} - Attach an EC2 Instance to the elb specified
DELETE http://hostname/elb/{elbName} - Dettach an EC2 Instance from the elb specified

The API is being served with Apache Web Server


