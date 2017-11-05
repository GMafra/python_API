#!flask/bin/python
# Importing the basic libraries
from flask import Flask, jsonify, make_response, request, abort
import boto3
from botocore.exceptions import ClientError

# Creating an app for flask
app = Flask(__name__)

elb_client = boto3.client('elb')
ec2_client = boto3.client('ec2')

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


# This method is executed whenever /elb/{elb_name} is executed.
@app.route('/elb/<elb_name>', methods=['GET', 'POST', 'DELETE'])
def elb_methods(elb_name):

    # Raises an error if load balancer does not exist
    assert elb_name == request.view_args['elb_name']

    if request.method == 'GET':
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

    if request.method == 'POST':
        try:
            elb_instances_ids = getelbInstanceIDs(elb_name)
            if request.json['instanceId'] in elb_instances_ids:
                abort(instance_attached(409))
            else:
                response = elb_client.register_instances_with_load_balancer(
                    Instances=[
                        {
                            'InstanceId': request.json['instanceId'],
                        },
                    ],
                    LoadBalancerName= elb_name,
                )
            return jsonify({'instance added' : get_instace_data(request.json['instanceId'])})
        except ClientError as e:
            if e.response ['Error']['Code'] in 'InvalidInstanceID':
                abort(400)

    if request.method == 'DELETE':
        try:
            elb_instances_ids = getelbInstanceIDs(elb_name)

            if request.json['instanceId'] not in elb_instances_ids:
                abort(instance_notattached(409))
            else:
                response = elb_client.deregister_instances_from_load_balancer(
                    Instances=[
                        {
                            'InstanceId': request.json['instanceId'],
                        },
                    ],
                    LoadBalancerName= elb_name,
                )
            return jsonify({'instance removed' : get_instace_data(request.json['instanceId'])})
        except ClientError as e:
            if e.response ['Error']['Code'] in 'InvalidInstanceID':
                abort(400)



# Main body that is executed when this function is called
if __name__ == '__main__':
    app.run(debug=True)