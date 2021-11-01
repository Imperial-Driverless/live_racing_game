from typing import List, NewType, Tuple

from numpy import number
from pydantic import BaseModel
from fastapi import FastAPI
import uvicorn
import threading
import time
import contextlib
from aiocache import Cache
import asyncio
import yaml
import numpy as np
import gym


app = FastAPI()
cache = Cache(Cache.MEMORY)

Steer = NewType('Steer', float)
Speed = NewType('Speed', float)
TeamId = NewType('TeamId', int)

class Command(BaseModel):
    speed: Speed
    steer: Steer

class PostPayload(BaseModel):
    cmd: Command
    team_id: TeamId

class Observation(BaseModel):
    scan: List[float]
    pose_x: float
    pose_y: float
    pose_theta: float
    linear_vel_x: float
    linear_vel_y: float
    ang_vel_z: float

@app.get("/")
async def read_root(team_id: TeamId) -> Observation:
    return await cache.get(f'obs{team_id}')

@app.post("/")
async def update_cmd(data: PostPayload):
    await cache.set(0, data.cmd)


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

    async def get_cmd(self) -> Tuple[Speed, Steer]:
        return await cache.get(self.id)



async def reset_team_cmds(num_teams):
    await asyncio.wait([cache.set(i, Command(speed=0, steer=0)) for i in range(num_teams)])



def extract_observation(obs, team_id: TeamId) -> Observation:
    return Observation(
        scan=obs['scans'][team_id].tolist(),
        pose_x=obs['poses_x'][team_id],
        pose_y=obs['poses_y'][team_id],
        pose_theta=obs['poses_theta'][team_id],
        linear_vel_x=obs['linear_vels_x'][team_id],
        linear_vel_y=obs['linear_vels_y'][team_id],
        ang_vel_z=obs['ang_vels_z'][team_id]
    )

async def main():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = Server(config=config)

    num_teams = 2

    team_agents = [TeamAgent(TeamId(i)) for i in range(num_teams)]
    await reset_team_cmds(num_teams)

    with open('config_example_map.yaml') as file:
        conf = yaml.load(file, Loader=yaml.FullLoader)

    starting_position = np.array([conf['sx'], conf['sy'], conf['stheta']])

    env = gym.make('f110_gym:f110-v0', map=conf['map_path'], map_ext=conf['map_ext'], num_agents=num_teams)
    obs, step_reward, done, info = env.reset(np.repeat([starting_position], num_teams, axis=0))

    env.render()

    laptime = 0.0
    start = time.time()


    with server.run_in_thread():
        try:
            while not done:
                cmds = await asyncio.gather(*[ta.get_cmd() for ta in team_agents])
                cmds_arr = [[c.steer, c.speed] for c in cmds]
                obs, step_reward, done, info = env.step(np.array(cmds_arr))
                await asyncio.wait([cache.set(f'obs{i}', extract_observation(obs, TeamId(i))) for i in range(num_teams)])
                laptime += step_reward
                env.render(mode='human')
        except KeyboardInterrupt:
            pass
    
    print('Sim elapsed time:', laptime, 'Real elapsed time:', time.time()-start)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
