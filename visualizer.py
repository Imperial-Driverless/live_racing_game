import argparse
import pickle

import requests

from f110_gym.envs.rendering import EnvRenderer

WINDOW_W = 1000
WINDOW_H = 800

parser = argparse.ArgumentParser(description='Live racing game visualizer')
parser.add_argument('host', type=str)
parser.add_argument('--port', type=int, default=8000)

args = parser.parse_args()

HOST_URL = f'http://{args.host}:{args.port}'

renderer = EnvRenderer(WINDOW_W, WINDOW_H)
renderer.update_map('example_map', '.png')
while True:
    try:
        obs = pickle.loads(requests.get(HOST_URL + '/all').content)
        renderer.update_obs(obs)
        renderer.dispatch_events()
        renderer.on_draw()
        renderer.flip()
    except KeyboardInterrupt:
        break
    except Exception as e:
        if str(e) == 'Rendering window was closed.':
            break

