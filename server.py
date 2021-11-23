from __future__ import annotations

from typing import List, NewType, Dict, Any
import argparse

from pydantic import BaseModel
from fastapi import FastAPI, Response
import uvicorn
import threading
import time
import contextlib
from aiocache import Cache
import asyncio
import yaml
import numpy as np
import gym
import json
import pickle



app = FastAPI()
cache = Cache(Cache.MEMORY)

Steer  = NewType('Steer', float)
Speed  = NewType('Speed', float)
TeamToken = NewType('TeamToken', int)
TeamId = NewType('TeamId', int)

tokens: List[TeamToken] = list(map(TeamToken, [145,281,392,417,565,684,777,892]))

teams: Dict[TeamToken, TeamId] = {t: TeamId(i) for i, t in enumerate(tokens)}

class Command(BaseModel):
    speed: Speed
    steer: Steer

class PostPayload(BaseModel):
    cmd: Command
    team_token: TeamToken

class Observation(BaseModel):
    scan: List[float]
    pose_x: float
    pose_y: float
    pose_theta: float
    linear_vel_x: float
    linear_vel_y: float
    ang_vel_z: float

    @classmethod
    def extract(cls, obs, team_id: TeamId) -> Observation:
        return Observation(
            scan=obs['scans'][team_id].tolist(),
            pose_x=obs['poses_x'][team_id],
            pose_y=obs['poses_y'][team_id],
            pose_theta=obs['poses_theta'][team_id],
            linear_vel_x=obs['linear_vels_x'][team_id],
            linear_vel_y=obs['linear_vels_y'][team_id],
            ang_vel_z=obs['ang_vels_z'][team_id])





@app.get("/")
async def read_root(team_token: TeamToken) -> Observation | Response:
    try:
        return await cache.get(f'obs{teams[team_token]}') # type: ignore
    except KeyError:
        return Response('invalid team token', status_code=403)

@app.get("/all")
async def get_all() -> Response:

    o: Dict[str, Any] = await cache.get('obs') # type: ignore
    try:
        del o['scans']
    except:
        pass
    os = pickle.dumps(o)
    return Response(content=os)

@app.post("/")
async def update_cmd(data: PostPayload):
    try:
        await cache.set(teams[data.team_token], data.cmd)
    except KeyError:
        return Response('invalid team token', status_code=403)







class Server(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    @contextlib.contextmanager
    def run_in_thread(self):
        thread = threading.Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                time.sleep(1e-3)
            yield
        finally:
            self.should_exit = True
            thread.join()

class TeamAgent:
    def __init__(self, id: TeamId):
        self.id: TeamId = id

    async def get_cmd(self) -> Command:
        return await cache.get(self.id) # type: ignore


async def reset_team_cmds(num_teams):
    await asyncio.wait([cache.set(i, Command(speed=0, steer=0)) for i in range(num_teams)])

async def set_team_observations(obs, num_teams):
    await asyncio.wait([cache.set(f'obs{i}', Observation.extract(obs, TeamId(i))) for i in range(num_teams)] + [cache.set('obs', obs)])






async def main():
    num_teams = len(teams)

    parser = argparse.ArgumentParser(description='Live racing game server')
    parser.add_argument('host', type=str)
    parser.add_argument('--port', type=int, default=8000)

    args = parser.parse_args()

    config = uvicorn.Config(app, args.host, args.port, log_level="error")
    server = Server(config)

    

    team_agents = [TeamAgent(TeamId(i)) for i in range(num_teams)]
    
    with open('config_example_map.yaml') as file:
        conf = yaml.load(file, Loader=yaml.FullLoader)

    starting_positions = np.array([conf['sx'], conf['sy'], conf['stheta']] * num_teams).reshape(num_teams, 3)

    env = gym.make('f110_gym:f110-v0', map=conf['map_path'], map_ext=conf['map_ext'], num_agents=num_teams, starting_positions=starting_positions)
    
    with server.run_in_thread(), open('laps.json', 'w+') as f:
        try:
            await reset_team_cmds(num_teams)

            obs, step_reward, done, info = env.reset()

            laptime = 0.0
            start = time.time()
            last_step = start

            while True:
                cmds = await asyncio.gather(*[ta.get_cmd() for ta in team_agents])
                cmds_arr = [[c.steer, c.speed] for c in cmds]

                now = time.time()
                obs, step_reward, done, info = env.step(np.array(cmds_arr), time_step=now - last_step) # type: ignore - introducing time_step abuses the api
                last_step = now

                f.seek(0)
                json.dump(obs['lap_counts'].tolist(), f)
                f.truncate()
                
                await set_team_observations(obs, num_teams)

                laptime += step_reward
                # env.render()
                
        except KeyboardInterrupt:
            pass
    
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
