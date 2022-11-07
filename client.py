import json
import time
import argparse

import requests

parser = argparse.ArgumentParser(description='Live racing game visualizer')
parser.add_argument('token', type=int)
parser.add_argument('host', type=str)
parser.add_argument('--port', type=int, default=8000)

args = parser.parse_args()

SERVER_URL = f'http://{args.host}:{args.port}'
TEAM_TOKEN = args.token

def get_observation() -> dict:
    """Returns a dict containing the following fields:
        - scan: a list of length 100, where the i-th element is the distance 
                to the nearest obstacle at an angle of -2.35 + i*0.047 from 
                the car's heading. (increasing counterclockwise)
        - pose_x: the x coordinate of the car's pose
        - pose_y: the y coordinate of the car's pose
        - pose_theta: the orientation of the car's pose
        - linear_vel_x: the x component of the car's linear velocity
        - linear_vel_y: the y component of the car's linear velocity
        - ang_vel_z: the car's angular velocity
    """
    r = requests.get(f'{SERVER_URL}/', params={'team_token': TEAM_TOKEN})
    if r.status_code == 403:
        raise Exception('Invalid team token')

    return json.loads(r.content)

def send_command(speed, steer):
    data= {
        'cmd': {'speed': speed, 'steer': steer},
        'team_token': TEAM_TOKEN
        }

    requests.post(f'{SERVER_URL}/', data=json.dumps(data))


speed = 3
steer_amplitude = 0.2
while True:
    o = get_observation()
    s = o['scan']
    l_sum = sum(s[30:40])
    r_sum = sum(s[60:70])
    steer = (-1 if l_sum > r_sum else 1) * steer_amplitude
    send_command(speed, steer)

    
