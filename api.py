#!flask/bin/python
from flask import Flask, jsonify, make_response, request, abort
import boto3
from botocore.exceptions import ClientError

app = Flask(__name__)

elb_client = boto3.client('elb')
ec2_client = boto3.client('ec2')

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'The ELB does not exist'}), 404)

@app.errorhandler(400)
def wrong_data(error):
    return make_response(jsonify({'error': 'Wrong data format'}), 400)

def instance_attached(error):
    return make_response(jsonify({'error': 'Instance is already on LoadBalancer'}), 409)

def instance_notattached(error):
    return make_response(jsonify({'error': 'Instance is not on LoadBalacer'}), 409)

@app.route('/healthcheck', methods=['GET'])
def get_health():
    return jsonify({'Status': 'The service is up!'})


def get_instace_data(instaceid):
    instance_data = []
    reservations = ec2_client.describe_instances(Filters=[{'Name' : 'instance-id', 'Values' : [instanceid]}])
    for reservation in reservations['Reservations']:
        for instance in reservation['Instances']:
            instance_data.append(
                {
                    'instanceId': instance['InstanceId'],
                    'instanceType': instance['InstanceType'],
                    'launchDate': instance['LaunchTime'].strftime('%Y-%m-%dT%H:%M:%S.%f')
                }
            )



@app.route('/elb/<elb_name>', methods=['GET', 'POST', 'DELETE'])
def elb_methods(elb_name):
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
            elb_instances_ids = []
            for elb in elbs:
                instances = elb['Instances']
                for instance in instances:
                    elb_instances_ids.append(instance['InstanceId'])

            reservations = ec2_client.describe_instances(
                InstanceIds=elb_instances_ids
            )['Reservations']

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


            return jsonify({'Machines' : all_instances})

    if request.method == 'POST':
        try:
            elbs =  elb_client.describe_load_balancers(
            LoadBalancerNames=[
            elb_name
            ]
        )['LoadBalancerDescriptions']
            elb_instances_ids = sum(list(map(lambda elb: list(map(lambda i: i['InstanceId'], elb['Instances'])), elbs)), [])
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
            return jsonify({'instance added' : request.json['instanceId']})
        except ClientError as e:
            if e.response ['Error']['Code'] in 'InvalidInstanceID':
                abort(400)





    if request.method == 'DELETE':
        try:
            elbs =  elb_client.describe_load_balancers(
        LoadBalancerNames=[
            elb_name
            ]
        )['LoadBalancerDescriptions']

            elb_instances_ids = sum(list(map(lambda elb: list(map(lambda i: i['InstanceId'], elb['Instances'])), elbs)), [])

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
            return jsonify({'instance removed' : request.json['instanceId']})
        except ClientError as e:
            if e.response ['Error']['Code'] in 'InvalidInstanceID':
                abort(400)



if __name__ == '__main__':
    app.run(debug=True)