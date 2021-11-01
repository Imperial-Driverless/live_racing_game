from typing import NewType
from pydantic import BaseModel
from fastapi import FastAPI
import uvicorn
import threading
import time
import contextlib
from aiocache import Cache
import asyncio


app = FastAPI()
cache = Cache(Cache.MEMORY)


@app.get("/")
def read_root():
    return {"Hello": "World"}
    

class Command(BaseModel):
    speed: float
    steer: float

TeamId = NewType('TeamId', int)

class PostPayload(BaseModel):
    cmd: Command
    team_id: TeamId


@app.post("/")
async def update_cmd(data: PostPayload):
    print(f'got {data.cmd.speed}, {data.cmd.steer} from team {data.team_id}')
    await cache.set(0, data.cmd)
    return None

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


async def reset_team_cmds(num_teams):
    await asyncio.wait([cache.set(i, Command(speed=0, steer=0)) for i in range(num_teams)])


async def main():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = Server(config=config)

    await reset_team_cmds(1)

    with server.run_in_thread():
        try:
            while True:
                time.sleep(1)
                print(await cache.get(0))
        except KeyboardInterrupt:
            pass



if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
