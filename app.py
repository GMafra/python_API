#!flask/bin/python
from flask import Flask, jsonify, make_response, request
import boto3

app = Flask(__name__)

elb_client = boto3.client('elb')
ec2_client = boto3.client('ec2')

@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'The ELB does not exist'}), 404)

@app.errorhandler(400)
def wrong_data(error):
    return make_response(jsonify({'error': 'Wrong data format'}), 400)

@app.errorhandler(409)
def instance_attached(error):
    return make_response(jsonify({'error': 'Instance is already on LoadBalancer'}), 409)

@app.errorhandler(408)
def instance_notattached(error):
    return make_response(jsonify({'error': 'Instance is not on LoadBalacer'}), 408)

@app.route('/healthcheck', methods=['GET'])
def get_health():
    return jsonify({'Status': 'The service is up!'})



@app.route('/elb/<elb_name>', methods=['GET'])
def get_elb(elb_name):
    assert elb_name == request.view_args['elb_name']
    elbs =  elb_client.describe_load_balancers(
    LoadBalancerNames=[
      elb_name
    ]
  )['LoadBalancerDescriptions']

    elb_instances_ids = sum(list(map(lambda elb: list(map(lambda i: i['InstanceId'], elb['Instances'])), elbs)), [])

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



#@app.route('/elb/<str:elb_name>', methods=['DELETE'])
#def remove_instances(instance_name):



#@app.route('/elb/<str:elb_name>', methods=['POST'])
#def attach_instance(instance_name):


if __name__ == '__main__':
    app.run(debug=True)
