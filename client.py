import json
import pickle
import time
import argparse
from typing import Any, List, Tuple

import requests
from f110_gym.envs.rendering import EnvRenderer




parser = argparse.ArgumentParser(description='Live racing game visualizer')
parser.add_argument('token', type=int)
parser.add_argument('host', type=str)
parser.add_argument('--port', type=int, default=8000)

args = parser.parse_args()

SERVER_URL = f'http://{args.host}:{args.port}'
TEAM_TOKEN = args.token
WINDOW_W = 1000
WINDOW_H = 800
renderer = EnvRenderer(WINDOW_W, WINDOW_H)
renderer.update_map('example_map', '.png')

def get_observation() -> dict:
    r = requests.get(f'{SERVER_URL}/')
    if r.status_code == 403:
        raise Exception('Invalid team token')

    return pickle.loads(r.content)

def send_command(speed, steer):
    data= {
        'cmd': {'speed': speed, 'steer': steer},
        'team_token': TEAM_TOKEN
        }

    requests.post(f'{SERVER_URL}/', data=json.dumps(data))

def render(o: Any, my_idx: int) -> None:
    # So that our car has a unique color     
    o['ego_idx'] = my_idx
    renderer.update_obs(o)
    renderer.dispatch_events()
    renderer.on_draw()
    renderer.flip()


class MyController:
    def __init__(self) -> None:
        self.speed = 7
        self.steer_amplitude = 0.2

    def get_controls(self, x: float, y: float, theta: float, scan: List[float]) -> Tuple[float, float]:
        """
        x, y and theta are basically what you expect them to be.
        scan is a list of 100 distances to obstacles in the car's FOV,
        such that the first element is the distance at the angle -2.35 rad and the last at 2.35 rad.
        The remaining elements are the distances at evenly spaced angles between those two.
        """
        
        # Implement your own logic here, this is just an example that works reasonably well
        l_sum = sum(scan[30:40])
        r_sum = sum(scan[60:70])
        steer = (-1 if l_sum > r_sum else 1) * self.steer_amplitude

        return self.speed, steer
        

def main():
    my_idx = requests.get(f'{SERVER_URL}/team_id', params={'team_token': TEAM_TOKEN}).json()
    controller = MyController()

    while True:
        o = get_observation()

        # you can disable rendering if you wish to, but it won't speed things up
        # because physics is simulated on the server
        render(o, my_idx)
        my_x, my_y, my_theta, my_scan = o['poses_x'][my_idx], o['poses_y'][my_idx], o['poses_theta'][my_idx], o['scans'][my_idx]
        speed, steer = controller.get_controls(my_x, my_y, my_theta, my_scan)
        send_command(speed, steer)

if __name__ == "__main__":
    main()
