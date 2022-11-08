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
from pathlib import Path


app = FastAPI()
cache = Cache(Cache.MEMORY)

Steer  = NewType('Steer', float)
Speed  = NewType('Speed', float)
TeamToken = NewType('TeamToken', int)
TeamId = NewType('TeamId', int)

tokens: List[TeamToken] = [TeamToken(int(t)) for t in Path('team_tokens.txt').read_text().split()]

teams: Dict[TeamToken, TeamId] = {t: TeamId(i) for i, t in enumerate(tokens)}

class Command(BaseModel):
    speed: Speed
    steer: Steer

class PostPayload(BaseModel):
    cmd: Command
    team_token: TeamToken



@app.get('/team_id')
async def get_team_id(team_token: TeamToken):
    try:
        return teams[team_token]
    except KeyError:
        return Response('invalid team token', status_code=403)

@app.get("/")
async def read_root() -> Response:
    o = await cache.get('obs') # type: ignore
    return Response(content=o)

@app.post("/")
async def update_cmd(data: PostPayload):
    try:
        data.cmd.speed = max(0.01, min(0.7, data.cmd.speed))
        data.cmd.steer = max(-0.3, min(0.3, data.cmd.speed))
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
    await asyncio.wait([cache.set(i, Command(speed=0.1, steer=0)) for i in range(num_teams)])






async def main():
    num_teams = len(teams)
    print(f'{num_teams=}')

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

            obs, step_reward, done, info = env.reset(starting_positions)

            laptime = 0.0
            start = time.time()
            last_step = start

            while True:
                cmds = await asyncio.gather(*[ta.get_cmd() for ta in team_agents])
                cmds_arr = [[c.steer, c.speed] for c in cmds]

                now = time.time()
                obs, step_reward, done, info = env.step(np.array(cmds_arr), 0.05) # type: ignore - introducing time_step abuses the api
                last_step = now

                f.seek(0)
                json.dump([int(x) for x in obs['lap_counts']], f)
                f.truncate()
                
                await cache.set('obs', pickle.dumps(obs)) # type: ignore

                laptime += step_reward
                # env.render()
                
        except KeyboardInterrupt:
            pass
    
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
