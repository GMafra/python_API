#!/usr/bin/python
# Importing the basic libraries
from flask import Flask, jsonify, make_response, request, abort
from flask_basicauth import BasicAuth
import boto3
from botocore.exceptions import ClientError

# Creating an app for flask
app = Flask(__name__)

app.config['BASIC_AUTH_USERNAME'] = 'user'
app.config['BASIC_AUTH_PASSWORD'] = 'test'

# Conguring session settings
session = boto3.setup_default_session(region_name='sa-east-1',aws_access_key_id='access_key',aws_secret_access_key='secret_key')
elb_client = boto3.client('elb')
ec2_client = boto3.client('ec2')

basic_auth = BasicAuth(app)

# Begin custom error messages functions
# Return ELB does not exist error 
@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'The ELB does not exist'}), 404)

# Return error on malformed json request on attaching and dettaching instances
@app.errorhandler(400)
def wrong_data(error):
    return make_response(jsonify({'error': 'Wrong data format'}), 400)

# Return instance already attached to loadbalancer error
def instance_attached(error):
    return make_response(jsonify({'error': 'Instance is already on LoadBalancer'}), 409)

# Return instance not attached to loadbalancer error
def instance_notattached(error):
    return make_response(jsonify({'error': 'Instance is not on LoadBalancer'}), 409)

# End custom error messages functions


# API health check function
@app.route('/healthcheck', methods=['GET'])
@basic_auth.required
def get_health():
    return jsonify({'Status': 'The service is up!'})

# Get MachineInfo from EC2 instances
def get_instace_data(instaceid):
    instance_data = []
    reservations = ec2_client.describe_instances(Filters=[{'Name' : 'instance-id', 'Values' : [instaceid]}])
    for reservation in reservations['Reservations']:
        for instance in reservation['Instances']:
            instance_data.append(
                {
                    'instanceId': instance['InstanceId'],
                    'instanceType': instance['InstanceType'],
                    'launchDate': instance['LaunchTime'].strftime('%Y-%m-%dT%H:%M:%S.%f')
                }
            )
    return instance_data

# Get all instances in Reservation
def getAllInstances(reservations):
    all_instances = []

    for reservation in reservations:
        for instance in reservation['Instances']:
            all_instances.append(
                {
                    'instanceId': instance['InstanceId'],
                    'instanceType': instance['InstanceType'],
                    'launchDate': instance['LaunchTime'].strftime('%Y-%m-%dT%H:%M:%S.%f')
                }
            )
    return all_instances

# Get the all the ids of instances attached to elb
def getAllInstanceIDs(elbs):
    elb_instances_ids = []
    for elb in elbs:
        instances = elb['Instances']
        for instance in instances:
            elb_instances_ids.append(instance['InstanceId'])
    return elb_instances_ids


# Get elb instances IDS from the load balancer name
def getelbInstanceIDs(elb_name):
    elbs = elb_client.describe_load_balancers(LoadBalancerNames=[elb_name])['LoadBalancerDescriptions']
    return sum(list(map(lambda elb: list(map(lambda i: i['InstanceId'], elb['Instances'])), elbs)), [])

# Function for the GET http method
def getHTTPmethod(elb_name):
    try:
        elbs = elb_client.describe_load_balancers(
        LoadBalancerNames=[
            elb_name
        ]
    )['LoadBalancerDescriptions']
    except ClientError as e:
        if e.response['Error']['Code'] == 'LoadBalancerNotFound':
            abort(404)
    else:
        elb_instances_ids = getAllInstanceIDs(elbs)
        reservations = ec2_client.describe_instances(
            InstanceIds=elb_instances_ids
        )['Reservations']

        all_instances = getAllInstances(reservations)

        return jsonify({'Machines' : all_instances})

# Function for the POST http method
def postHTTPmethod(elb_name, instanceid):
    try:
        elb_instances_ids = getelbInstanceIDs(elb_name)
        if request.json['instanceId'] in elb_instances_ids:
            abort(instance_attached(409))
        else:
            response = elb_client.register_instances_with_load_balancer(
                Instances=[
                    {
                        'InstanceId': instanceid,
                    },
                ],
                LoadBalancerName= elb_name,
            )
        return jsonify({'instance added' : get_instace_data(instanceid)})
    except ClientError as e:
        if e.response ['Error']['Code'] in 'InvalidInstanceID':
            abort(400)

#Function for the DELETE http method
def deleteHTTPmethod(elb_name,instanceid):
    try:
        elb_instances_ids = getelbInstanceIDs(elb_name)
        if request.json['instanceId'] not in elb_instances_ids:
            abort(instance_notattached(409))
        else:
            response = elb_client.deregister_instances_from_load_balancer(
                Instances=[
                    {
                        'InstanceId': instanceid,
                    },
                ],
                LoadBalancerName= elb_name,
            )
        return jsonify({'instance removed' : get_instace_data(instanceid)})
    except ClientError as e:
        if e.response ['Error']['Code'] in 'InvalidInstanceID':
            abort(400)


# This method is executed whenever /elb/{elb_name} is executed.
@app.route('/elb/<elb_name>', methods=['GET', 'POST', 'DELETE'])
@basic_auth.required
def elb_methods(elb_name):
    assert elb_name == request.view_args['elb_name']
    # Calls get method
    if request.method == 'GET':
        return getHTTPmethod(elb_name)
    else:
        instanceid = request.json['instanceId']

    # Calls post method
    if request.method == 'POST':
        return postHTTPmethod(elb_name, instanceid)
        
    # Delete method
    if request.method == 'DELETE':
        return deleteHTTPmethod(elb_name, instanceid)



# Main body that is executed when this function is called
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
